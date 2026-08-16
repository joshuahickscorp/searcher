"""API campaign runner: reference wave, then the real orchestrator.

If live discovery is disabled or a layer cannot be imported, the runner
stops with an honest BLOCKED verdict. It never invents COMPLETE.
"""

from __future__ import annotations

import os
import re
import threading
import traceback
from pathlib import Path

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.orchestrator import CampaignOrchestrator, layers_present
from searcher.campaigns.states import is_terminal
from searcher.contracts.enums import (
    CampaignState,
    EvidencePolarity,
    FactClass,
    PublicEventName,
    SourceOutcome,
)
from searcher.contracts.models import (
    IntentBudget,
    PrivacySettings,
    ReferenceAnalysis,
    SearchConstraints,
    SearchIntent,
)
from searcher.core.budgets import Budget
from searcher.core.config import Settings
from searcher.core.errors import (
    BudgetExceeded,
    CancelledError,
    ErrorClass,
    InputError,
    MalformedContentError,
    SearcherError,
)
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.evidence.lineage import raw_lineage
from searcher.evidence.records import EvidenceRecord
from searcher.receipts.types import CampaignTerminalReceipt
from searcher.reference.gaps import evidence_gaps
from searcher.reference.ingest import ingest_bytes
from searcher.workers.reference.pipeline import run_reference_query_wave

# Create-time field bounds. Images are capped by Settings; these stop text/tag bombs.
MAX_INTENT_TEXT_CHARS = 16_384
MAX_TAG_COUNT = 64
MAX_TAG_CHARS = 256
_INTERNAL_FAILURES = frozenset(
    {
        ErrorClass.INTERNAL_INVARIANT,
        ErrorClass.DATABASE,
        ErrorClass.STORAGE,
        ErrorClass.MODEL,
        ErrorClass.BROWSER,
    }
)
_ABS_PATH = re.compile(r"(?:/Users|/home|/var|/tmp|/private|/opt|/etc)/[^\s:'\"]+")
_BIDI_OVERRIDES = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
_ALLOWED_CONTROLS = frozenset("\t\n\r")
# ContentStore's object index and hard-link zone have no lock. Concurrent
# creates of the same bytes raise FileExistsError / torn JSON and return 500.
_STORE_LOCK = threading.RLock()

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


def _reject_hostile_fields(text: str | None, tags: list[str]) -> None:
    """Refuse text/tag bombs before a campaign row is written."""
    if text is not None:
        _reject_hostile_string(text, field="text", max_chars=MAX_INTENT_TEXT_CHARS)
    if len(tags) > MAX_TAG_COUNT:
        raise InputError(f"A search can include at most {MAX_TAG_COUNT} tags.")
    for tag in tags:
        _reject_hostile_string(tag, field="tag", max_chars=MAX_TAG_CHARS)


def _reject_hostile_string(value: str, *, field: str, max_chars: int) -> None:
    if "\x00" in value:
        raise InputError(f"{field} contains a NUL byte.")
    if any(ch in _BIDI_OVERRIDES for ch in value):
        raise InputError(f"{field} contains a bidirectional override character.")
    if any(ord(ch) < 32 and ch not in _ALLOWED_CONTROLS for ch in value):
        raise InputError(f"{field} contains a control character.")
    if len(value) > max_chars:
        raise InputError(f"{field} exceeds the {max_chars}-character cap.")


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
    _reject_hostile_fields(text, tags)
    search_id = new_id()
    intent = SearchIntent(
        search_id=search_id,
        created_at=utc_now(),
        images=[],
        text=text,
        tags=list(tags),
        constraints=SearchConstraints(),
        budget=IntentBudget(
            wall_seconds=180 if cfg.live_discovery else 120,
            source_limit=8 if cfg.live_discovery else 0,
            page_limit=40 if cfg.live_discovery else 0,
            browser_page_limit=0,
            image_limit=max(cfg.max_images_per_search, 20),
            model_call_limit=0,
            byte_limit=max(cfg.max_total_upload_bytes, 8_000_000 if cfg.live_discovery else 0),
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
        with _STORE_LOCK:
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
                controller.record_evidence(
                    EvidenceRecord(
                        evidence_id=new_id(),
                        search_id=search_id,
                        content_digest=ref.digest,
                        family_id=ref.digest,
                        polarity=EvidencePolarity.SUPPORTING,
                        fact_class=FactClass.USER_SUPPLIED,
                        accepted=True,
                        lineage=raw_lineage(
                            input_digests=[ref.digest], process="reference_ingest"
                        ),
                        created_at=utc_now(),
                        label="reference_image",
                    )
                )
    except (InputError, MalformedContentError, BudgetExceeded) as exc:
        _stop_blocked(controller, search_id, _public_input_reason(exc), code="invalid_input")
        raise
    except SearcherError as exc:
        if exc.error_class is ErrorClass.STORAGE:
            _stop_blocked(
                controller,
                search_id,
                "The server does not have enough storage to keep this search.",
                code="storage_pressure",
            )
            raise
        _fail(
            controller,
            search_id,
            "The search failed because of an internal error. This is not a no-results outcome.",
            exc=exc,
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


def _looks_like_unusable_image(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {"UnidentifiedImageError", "DecompressionBombError"}:
        return True
    text = str(exc).lower()
    return (
        "cannot identify image" in text
        or "image file is truncated" in text
        or "broken data stream" in text
    )


def _public_input_reason(exc: BaseException) -> str:
    raw = str(exc)
    if raw.startswith("["):
        closing = raw.find("]")
        if closing != -1:
            raw = raw[closing + 1 :].strip()
    if "search_id=" in raw:
        raw = raw.split("search_id=", 1)[0].rstrip(" (").strip()
    cleaned = _ABS_PATH.sub("<path>", raw)
    return cleaned or "The search could not use the supplied input."


def _safe_error_text(exc: BaseException | None) -> str:
    if exc is None:
        return ""
    return _ABS_PATH.sub("<path>", f"{type(exc).__name__}: {exc}")


def _record_failure_trace(search_id: str, exc: BaseException | None, note: str) -> None:
    """Optional operator hook. Never used as the campaign's record of the error."""
    dest = os.environ.get("SEARCHER_FAIL_TRACE")
    if not dest:
        return
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [f"search_id={search_id}", f"note={note}"]
    if exc is not None:
        body.append(f"exc_type={type(exc).__name__}")
        body.append(f"exc={_safe_error_text(exc)}")
        body.append(traceback.format_exc())
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(body) + "\n---\n")


def _seal_terminal(
    controller: CampaignController,
    search_id: str,
    target: CampaignState,
    reason: str,
    *,
    error_class: ErrorClass | None = None,
    error: str | None = None,
    checkpoint_reason: str,
) -> None:
    campaign = controller.get(search_id)
    if is_terminal(campaign.state):
        return
    ctx = controller.context_from_disk(search_id)
    ctx.reason = reason
    ctx.error_class = error_class
    updated = controller.transition(search_id, target, context=ctx, actor="api")
    receipt = CampaignTerminalReceipt(
        search_id=search_id,
        terminal_status=target.value,
        terminal_reason=reason,
        state_version=updated.state_version,
        payload={"error": error or "", "error_class": error_class.value if error_class else ""},
    ).seal()
    controller.store_receipt(receipt)
    controller.checkpoint(search_id, "terminal", {"reason": checkpoint_reason})
    controller.emit(
        search_id,
        PublicEventName.SEARCH_COMPLETE.value,
        payload={"terminal_status": target.value, "reason": updated.terminal_reason or reason},
        actor="api",
        error=error,
    )


def _stop_blocked(
    controller: CampaignController,
    search_id: str,
    reason: str,
    *,
    code: str,
) -> None:
    try:
        _seal_terminal(
            controller,
            search_id,
            CampaignState.BLOCKED,
            reason,
            checkpoint_reason=code,
        )
    except SearcherError as exc:
        _record_failure_trace(search_id, exc, "BLOCKED transition failed")


def _fail(
    controller: CampaignController,
    search_id: str,
    reason: str,
    *,
    exc: BaseException | None = None,
) -> None:
    _record_failure_trace(search_id, exc, reason)
    error_class = ErrorClass.INTERNAL_INVARIANT
    if isinstance(exc, SearcherError) and exc.error_class in _INTERNAL_FAILURES:
        error_class = exc.error_class
    try:
        _seal_terminal(
            controller,
            search_id,
            CampaignState.FAILED,
            reason,
            error_class=error_class,
            error=_safe_error_text(exc),
            checkpoint_reason="internal_error",
        )
    except SearcherError as transition_exc:
        _record_failure_trace(search_id, transition_exc, "FAILED transition itself failed")


def _should_run_live(settings: Settings) -> bool:
    if not settings.live_discovery:
        return False
    present = layers_present()
    return present["discovery"] and present["routing"]


def run_api_campaign(controller: CampaignController, search_id: str) -> None:
    """Run the orchestrator when layers are live; otherwise stop with BLOCKED."""
    try:
        controller.cancellation.raise_if_cancelled(search_id)
        campaign = controller.get(search_id)
        if is_terminal(campaign.state) or controller.repos.is_deleted(search_id):
            return
        if _should_run_live(controller.settings):
            CampaignOrchestrator(
                controller,
                source_names=[
                    "wikimedia",
                    "kind",
                    "komehyo",
                    "the_realreal",
                    "byronesque",
                    "heroine",
                    "ebay",
                ],
                max_rounds=2,
                max_work=8,
                batch_size=3,
            ).run(search_id)
            return
        with _STORE_LOCK:
            run_reference_query_wave(controller, search_id, [], settings=controller.settings)
        if controller.repos.is_deleted(search_id):
            return
        from searcher.index.consult import consult_and_surface

        with _STORE_LOCK:
            consult_and_surface(controller, search_id)
        if controller.repos.is_deleted(search_id):
            return
        campaign = controller.get(search_id)
        if is_terminal(campaign.state):
            return
        controller.cancellation.raise_if_cancelled(search_id)
        coverage = blocked_discovery_coverage()
        runtime = controller.repos.get_runtime(search_id)
        prior = runtime.get("coverage")
        if isinstance(prior, dict) and prior.get("candidates_normalized"):
            coverage["candidates_normalized"] = prior["candidates_normalized"]
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
        _seal_terminal(
            controller,
            search_id,
            CampaignState.BLOCKED,
            DISCOVERY_BLOCKED_REASON,
            checkpoint_reason="discovery_unavailable",
        )
    except CancelledError:
        return
    except (InputError, MalformedContentError, BudgetExceeded) as exc:
        _stop_blocked(controller, search_id, _public_input_reason(exc), code="invalid_input")
    except SearcherError as exc:
        if exc.error_class is ErrorClass.CANCELLED:
            return
        if exc.error_class is ErrorClass.STORAGE:
            _stop_blocked(
                controller,
                search_id,
                "The server does not have enough storage to keep this search.",
                code="storage_pressure",
            )
            return
        _fail(
            controller,
            search_id,
            "The search failed because of an internal error. This is not a no-results outcome.",
            exc=exc,
        )
    except Exception as exc:
        if _looks_like_unusable_image(exc):
            _stop_blocked(
                controller,
                search_id,
                "A supplied image could not be decoded. This is not a no-results outcome.",
                code="malformed_content",
            )
            return
        _fail(
            controller,
            search_id,
            "The search failed because of an internal error. This is not a no-results outcome.",
            exc=exc,
        )
