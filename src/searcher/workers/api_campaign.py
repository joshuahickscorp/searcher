"""API campaign runner: reference wave, then an honest BLOCKED stop.

Discovery, retrieval, matching, authenticity, and ranking belong to other
waves. This runner never invents a result or a COMPLETE verdict.
"""

from __future__ import annotations

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.states import is_terminal
from searcher.contracts.enums import CampaignState, PublicEventName, SourceOutcome
from searcher.contracts.models import (
    IntentBudget,
    PrivacySettings,
    ReferenceAnalysis,
    SearchConstraints,
    SearchIntent,
)
from searcher.core.budgets import Budget
from searcher.core.config import Settings
from searcher.core.errors import CancelledError, ErrorClass, InputError, SearcherError
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.receipts.types import CampaignTerminalReceipt
from searcher.reference.gaps import evidence_gaps
from searcher.reference.ingest import ingest_bytes
from searcher.workers.reference.pipeline import run_reference_query_wave

DISCOVERY_BLOCKED_REASON = (
    "Live listing discovery is not available in this process. "
    "Reference analysis finished. This is not a finding that the item does not exist."
)

DISCOVERY_WARNING = "Live listing search did not run because the discovery layer is not present."


def empty_coverage() -> dict[str, object]:
    return {
        "sources_completed": [],
        "sources_blocked": [],
        "sources_in_progress": [],
        "pages_fetched": 0,
        "candidates_normalized": 0,
        "candidates_hidden": 0,
    }


def blocked_discovery_coverage() -> dict[str, object]:
    coverage = empty_coverage()
    coverage["sources_blocked"] = [
        {
            "id": "live_discovery",
            "name": "Live listing discovery",
            "status": SourceOutcome.SOURCE_UNAVAILABLE.value,
            "detail": DISCOVERY_WARNING,
        }
    ]
    return coverage


def create_api_campaign(
    controller: CampaignController,
    *,
    uploads: list[tuple[bytes, str | None]],
    text: str | None,
    tags: list[str],
    client_search_id: str | None,
    settings: Settings | None = None,
) -> str:
    cfg = settings or controller.settings
    search_id = new_id()
    intent = SearchIntent(
        search_id=search_id,
        created_at=utc_now(),
        images=[],
        text=text,
        tags=list(tags),
        constraints=SearchConstraints(),
        budget=IntentBudget(
            wall_seconds=120,
            source_limit=0,
            page_limit=0,
            browser_page_limit=0,
            image_limit=cfg.max_images_per_search,
            model_call_limit=0,
            byte_limit=cfg.max_total_upload_bytes,
            monetary_limit=None,
        ),
        privacy=PrivacySettings(),
    )
    budget = Budget.from_dict(
        {
            **intent.budget.model_dump(mode="json"),
            "retry_limit": 2,
            "storage_limit": 200_000_000,
            "per_host_rate": {},
        }
    )
    campaign = controller.create(intent, budget=budget, client_search_id=client_search_id)
    if campaign.search_id != search_id:
        return campaign.search_id
    digests: list[str] = []
    total = 0
    try:
        for data, declared_name in uploads:
            ref = ingest_bytes(
                controller.store,
                data,
                search_id=search_id,
                settings=cfg,
                declared_name=declared_name,
            )
            digests.append(ref.digest)
            total += len(data)
    except SearcherError:
        _fail(
            controller,
            search_id,
            "The search failed because of an internal error. This is not a no-results outcome.",
        )
        raise
    controller.set_runtime(
        search_id,
        has_visual_representation=True,
        reference_digests=digests,
        reference_bytes=total,
        image_count=len(digests),
        coverage=empty_coverage(),
        progress={"stage": "Understanding the item", "detail": None},
        deeper_refresh_available=False,
        missing_reference_views=[],
        counts={"real": 0, "possibly_real": 0, "hidden": 0},
    )
    return search_id


def _missing_views(controller: CampaignController, search_id: str) -> list[dict[str, str]]:
    try:
        raw = controller.store.get_private(search_id, "analysis.json")
    except (FileNotFoundError, KeyError):
        return []
    analysis = ReferenceAnalysis.model_validate_json(raw)
    views: list[dict[str, str]] = []
    for gap in evidence_gaps(analysis):
        if not gap.gap.startswith("missing_"):
            continue
        views.append({"view": gap.gap.removeprefix("missing_"), "why": gap.impact})
        if len(views) >= 3:
            break
    return views


def _fail(controller: CampaignController, search_id: str, reason: str) -> None:
    campaign = controller.get(search_id)
    if is_terminal(campaign.state):
        return
    ctx = controller.context_from_disk(search_id)
    ctx.error_class = ErrorClass.INTERNAL_INVARIANT
    ctx.reason = reason
    try:
        updated = controller.transition(search_id, CampaignState.FAILED, context=ctx, actor="api")
    except SearcherError:
        return
    controller.emit(
        search_id,
        PublicEventName.SEARCH_COMPLETE.value,
        payload={
            "terminal_status": CampaignState.FAILED.value,
            "reason": updated.terminal_reason or reason,
        },
        actor="api",
    )


def run_api_campaign(controller: CampaignController, search_id: str) -> None:
    """Run what exists, then stop with BLOCKED. Never claims search complete."""
    try:
        controller.cancellation.raise_if_cancelled(search_id)
        campaign = controller.get(search_id)
        if is_terminal(campaign.state) or controller.repos.is_deleted(search_id):
            return
        run_reference_query_wave(controller, search_id, [], settings=controller.settings)
        if controller.repos.is_deleted(search_id):
            return
        campaign = controller.get(search_id)
        if is_terminal(campaign.state):
            return
        controller.cancellation.raise_if_cancelled(search_id)
        coverage = blocked_discovery_coverage()
        missing = _missing_views(controller, search_id)
        controller.set_runtime(
            search_id,
            coverage=coverage,
            missing_reference_views=missing,
            deeper_refresh_available=False,
        )
        controller.emit(
            search_id,
            PublicEventName.SEARCH_COVERAGE.value,
            payload=coverage,
            actor="api",
        )
        controller.emit(
            search_id,
            PublicEventName.SEARCH_WARNING.value,
            payload={"code": "discovery_unavailable", "message": DISCOVERY_WARNING},
            actor="api",
        )
        ctx = controller.context_from_disk(search_id)
        ctx.reason = DISCOVERY_BLOCKED_REASON
        updated = controller.transition(search_id, CampaignState.BLOCKED, context=ctx, actor="api")
        receipt = CampaignTerminalReceipt(
            search_id=search_id,
            terminal_status=CampaignState.BLOCKED.value,
            terminal_reason=DISCOVERY_BLOCKED_REASON,
            state_version=updated.state_version,
        ).seal()
        controller.store_receipt(receipt)
        controller.checkpoint(search_id, "terminal", {"reason": "discovery_unavailable"})
        controller.emit(
            search_id,
            PublicEventName.SEARCH_COMPLETE.value,
            payload={
                "terminal_status": CampaignState.BLOCKED.value,
                "reason": DISCOVERY_BLOCKED_REASON,
            },
            actor="api",
        )
    except CancelledError:
        return
    except InputError:
        raise
    except SearcherError as exc:
        if exc.error_class is ErrorClass.CANCELLED:
            return
        _fail(
            controller,
            search_id,
            "The search failed because of an internal error. This is not a no-results outcome.",
        )
    except Exception:
        _fail(
            controller,
            search_id,
            "The search failed because of an internal error. This is not a no-results outcome.",
        )
