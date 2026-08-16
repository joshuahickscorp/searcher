"""Projections from stored contracts onto the frontend JSON contract."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.events import CampaignEvent
from searcher.campaigns.states import is_terminal
from searcher.contracts.enums import BucketPublic, CampaignState, PublicEventName
from searcher.contracts.models import BucketDecision, ListingCandidate, SearchCampaign
from searcher.core.time import format_utc
from searcher.workers.api_campaign import empty_coverage

STAGE_FROM_STATE: dict[str, str] = {
    CampaignState.CREATED.value: "Understanding the item",
    CampaignState.VALIDATING_INPUT.value: "Understanding the item",
    CampaignState.INGESTING_REFERENCES.value: "Understanding the item",
    CampaignState.CALIBRATING_REFERENCES.value: "Understanding the item",
    CampaignState.DECOMPOSING_REFERENCES.value: "Reading visible labels",
    CampaignState.FORMING_HYPOTHESES.value: "Building possible identities",
    CampaignState.PLANNING_QUERIES.value: "Searching exact names",
    CampaignState.PLANNING_SOURCES.value: "Searching international sources",
    CampaignState.DISCOVERING.value: "Searching international sources",
    CampaignState.ACQUIRING.value: "Comparing candidate images",
    CampaignState.NORMALIZING.value: "Comparing candidate images",
    CampaignState.DEDUPLICATING.value: "Comparing candidate images",
    CampaignState.BROAD_RETRIEVAL.value: "Comparing candidate images",
    CampaignState.FINE_MATCHING.value: "Checking detail consistency",
    CampaignState.AUTHENTICITY_REVIEW.value: "Checking listing authenticity evidence",
    CampaignState.LIVE_CHECKING.value: "Verifying live links",
    CampaignState.RANKING.value: "Ranking results",
    CampaignState.PUBLISHING.value: "Ranking results",
    CampaignState.GAP_ANALYSIS.value: "Ranking results",
    CampaignState.REPLANNING.value: "Searching alternate names",
}

_DROP_KEYS = frozenset({"path", "fixture_root", "image_paths"})


def safe_http_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value


def safe_image_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("/") and not value.startswith("//"):
        lowered = value.lower()
        if lowered.startswith("/javascript:") or ":" in value.split("/", 2)[0]:
            return None
        return value
    return safe_http_url(value)


def strip_private(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in _DROP_KEYS}


def result_counts(controller: CampaignController, search_id: str) -> dict[str, int]:
    counts = {"real": 0, "possibly_real": 0, "hidden": 0}
    for row in controller.repos.list_results(search_id):
        bucket = str(row["public_bucket"])
        if bucket in counts:
            counts[bucket] += 1
    return counts


def _as_coverage(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        return empty_coverage()
    if "sources_completed" in raw or "sources_blocked" in raw:
        coverage = empty_coverage()
        coverage.update(raw)
        return coverage
    coverage = empty_coverage()
    source = str(raw.get("source") or "")
    pages = int(raw.get("pages") or 0)
    if source:
        coverage["sources_completed"] = [
            {"id": source, "name": source, "status": "SEARCHED_MATCHES_FOUND", "detail": ""}
        ]
        coverage["pages_fetched"] = pages
    return coverage


def _progress_for(controller: CampaignController, campaign: SearchCampaign) -> dict[str, Any]:
    runtime = controller.repos.get_runtime(campaign.search_id)
    stored = runtime.get("progress")
    if isinstance(stored, dict) and stored.get("stage"):
        return {"stage": stored.get("stage"), "detail": stored.get("detail")}
    stage = STAGE_FROM_STATE.get(campaign.state.value)
    if campaign.terminal_status is not None:
        return {"stage": stage, "detail": None}
    return {"stage": stage, "detail": None}


def project_search(controller: CampaignController, campaign: SearchCampaign) -> dict[str, Any]:
    search_id = campaign.search_id
    runtime = controller.repos.get_runtime(search_id)
    meta = controller.repos.get_campaign_meta(search_id) or {}
    intent = controller.repos.get_intent(search_id)
    counts = result_counts(controller, search_id)
    coverage = _as_coverage(runtime.get("coverage") or campaign.coverage)
    hidden_note = runtime.get("hidden_policy_note")
    if not hidden_note and counts["hidden"]:
        hidden_note = "Some candidates did not meet policy."
    missing = runtime.get("missing_reference_views") or []
    terminal = campaign.terminal_status.value if campaign.terminal_status else None
    return {
        "search_id": search_id,
        "state": campaign.state.value,
        "state_version": campaign.state_version,
        "terminal_status": terminal,
        "terminal_reason": campaign.terminal_reason,
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "progress": _progress_for(controller, campaign),
        "coverage": coverage,
        "counts": counts,
        "hidden_policy_note": hidden_note,
        "missing_reference_views": missing,
        "deeper_refresh_available": bool(runtime.get("deeper_refresh_available")),
        "intent": {"text": intent.text or "", "tags": list(intent.tags)},
        "events_url": f"/v1/searches/{search_id}/events",
        "results_url": f"/v1/searches/{search_id}/results",
    }


def create_body(search_id: str, state: str) -> dict[str, str]:
    return {
        "search_id": search_id,
        "state": state,
        "events_url": f"/v1/searches/{search_id}/events",
        "results_url": f"/v1/searches/{search_id}/results",
    }


def _judgment_label(lower: float | None, *, contradictions: bool, missing: bool) -> str:
    if contradictions:
        return "Contradictory"
    if lower is None:
        return "Incomplete evidence"
    if missing and lower < 0.80:
        return "Incomplete evidence"
    if lower >= 0.80:
        return "High"
    if lower >= 0.45:
        return "Moderate"
    return "Incomplete evidence"


def _score_block(
    rows: list[dict[str, Any]], kind: str
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    chosen: dict[str, Any] | None = None
    for row in rows:
        if row["kind"] != kind:
            continue
        if chosen is None:
            chosen = row
            continue
        payload = str(row.get("payload_json") or "")
        finer = "match_evidence_id" in payload or "authenticity_evidence_id" in payload
        higher = float(row["lower_bound"]) >= float(chosen["lower_bound"])
        if finer or higher:
            chosen = row
    if chosen is None:
        return None, {}
    parsed: dict[str, Any] = {}
    raw_payload = chosen.get("payload_json")
    if raw_payload:
        try:
            loaded = json.loads(str(raw_payload))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            parsed = loaded
    return chosen, parsed


def _classified_value(fact: object) -> str | None:
    value = getattr(fact, "value", None)
    if value is None:
        return None
    return str(value)


def _format_price(amount: Decimal | None, currency: str | None) -> dict[str, str] | None:
    if amount is None and not currency:
        return None
    original = "" if amount is None else format(amount, "f").rstrip("0").rstrip(".")
    if amount is not None and amount == amount.to_integral_value():
        original = str(int(amount))
    display = original
    if currency == "JPY" and original:
        try:
            display = f"¥{int(Decimal(original)):,}"
        except Exception:
            display = f"JPY {original}"
    elif currency == "EUR" and original:
        display = f"€{original}"
    elif currency == "USD" and original:
        display = f"${original}"
    elif currency and original:
        display = f"{currency} {original}"
    elif currency:
        display = currency
    return {"original": original, "currency": currency or "", "display": display}


def _format_size(marked: str | None) -> dict[str, str] | None:
    if not marked:
        return None
    return {"marked": marked, "system": "", "display": f"Size {marked}"}


def project_result(
    controller: CampaignController,
    search_id: str,
    result_id: str,
    *,
    candidate_id: str,
    bucket: str,
    rank: int,
    decision: BucketDecision | None,
    candidate: ListingCandidate | None,
) -> dict[str, Any]:
    scores = [
        row
        for row in controller.repos.list_scores(search_id)
        if row.get("candidate_id") == candidate_id
    ]
    match_row, match_payload = _score_block(scores, "ITEM_MATCH")
    auth_row, auth_payload = _score_block(scores, "AUTHENTICITY_CONFIDENCE")
    util_row, util_payload = _score_block(scores, "LISTING_UTILITY")

    match_contradictions = list(match_payload.get("hard_contradictions") or [])
    auth_contradictions = list(auth_payload.get("hard_contradictions") or [])
    missing = list(auth_payload.get("missing_evidence") or [])
    if decision is not None:
        missing = list(decision.explanation.missing_evidence or missing)
        match_contradictions = list(decision.explanation.contradictions or match_contradictions)

    match_lower = float(match_row["lower_bound"]) if match_row else None
    auth_lower = float(auth_row["lower_bound"]) if auth_row else None
    item_match = None
    if match_row is not None:
        item_match = {
            "label": _judgment_label(
                match_lower, contradictions=bool(match_contradictions), missing=bool(missing)
            ),
            "mean": float(match_row["mean"]),
            "lower_bound": float(match_row["lower_bound"]),
            "upper_bound": float(match_row["upper_bound"]),
        }
    authenticity = None
    if auth_row is not None:
        authenticity = {
            "label": _judgment_label(
                auth_lower, contradictions=bool(auth_contradictions), missing=bool(missing)
            ),
            "mean": float(auth_row["mean"]),
            "lower_bound": float(auth_row["lower_bound"]),
            "upper_bound": float(auth_row["upper_bound"]),
        }

    availability = candidate.availability.value if candidate is not None else "UNKNOWN"
    last_checked = None
    if candidate is not None:
        last_checked = format_utc(candidate.last_checked_at)
    live = availability == "LIVE"
    utility_score = float(util_row["mean"]) if util_row else (1.0 if live else 0.0)
    listing_utility = {
        "live": live,
        "label": "Live" if live else ("Unknown" if availability == "UNKNOWN" else "Not live"),
        "score": utility_score,
        "last_checked_at": last_checked or util_payload.get("last_checked_at"),
    }

    support = list((decision.explanation.support if decision else None) or [])
    if not support:
        support = list(match_payload.get("hard_support") or match_payload.get("soft_support") or [])
    chips: list[dict[str, str]] = []
    for text in support[:3]:
        chips.append({"kind": "support", "text": str(text)})
    if not chips:
        for text in missing[:1]:
            chips.append({"kind": "missing", "text": str(text)})
    primary_gap = None
    if auth_contradictions:
        primary_gap = {"kind": "contradiction", "text": str(auth_contradictions[0])}
    elif missing:
        primary_gap = {"kind": "missing", "text": str(missing[0])}

    title = _classified_value(candidate.title) if candidate else None
    listing_url = safe_http_url(candidate.canonical_url if candidate else None)
    primary_image = None
    if candidate is not None and candidate.images:
        remote = safe_image_url(candidate.images[0].remote_url)
        if remote:
            primary_image = {"url": remote, "alt": title or "Listing image"}

    seller_reported: list[dict[str, str]] = []
    if candidate is not None:
        for field, fact in (
            ("Title", candidate.title),
            ("Brand", candidate.seller_reported_brand),
            ("Model", candidate.seller_reported_model),
            ("Size", None),
        ):
            if field == "Size" and candidate.size_original:
                seller_reported.append(
                    {
                        "field": "Size",
                        "value": str(candidate.size_original),
                        "origin": "REPORTED_BY_SELLER",
                    }
                )
                continue
            if fact is None:
                continue
            value = _classified_value(fact)
            if value:
                seller_reported.append(
                    {"field": field, "value": value, "origin": "REPORTED_BY_SELLER"}
                )

    heading = "Why Real" if bucket == BucketPublic.REAL.value else "Why Possibly Real"
    tab_reason = "This listing met the Real gate under the available evidence."
    if bucket == BucketPublic.POSSIBLY_REAL.value:
        tab_reason = "The item may match, but important evidence is missing or conflicting."
    if bucket == BucketPublic.REPLICA.value:
        heading = "Why Replica"
        tab_reason = "From replica sources. A replica listing can never be ranked Real."
    if decision is not None and decision.reason_codes:
        tab_reason = f"{tab_reason} Reason codes: {', '.join(decision.reason_codes)}."

    families = 0
    if candidate is not None:
        family_ids = {
            img.duplicate_family_id for img in candidate.images if img.duplicate_family_id
        }
        families = max(0, len(family_ids) - 1) if family_ids else 0

    why = {
        "heading": heading,
        "points": support,
        "tab_reason": tab_reason,
        "still_unverified": ["No physical inspection."],
        "supporting": support,
        "contradictions": list(dict.fromkeys([*match_contradictions, *auth_contradictions])),
        "missing": missing,
        "seller_reported": seller_reported,
        "images_compared": [],
        "duplicate_image_family_count": families,
        "live": live,
        "checked_at": last_checked,
    }

    source_name = candidate.source_adapter if candidate is not None else ""
    return {
        "result_id": result_id,
        "search_id": search_id,
        "candidate_id": candidate_id,
        "bucket": bucket,
        "rank": rank,
        "title": title or "",
        "source": {"name": source_name, "adapter": source_name},
        "listing_url": listing_url,
        "primary_image": primary_image,
        "price": _format_price(
            candidate.price_original if candidate else None,
            candidate.currency_original if candidate else None,
        ),
        "size": _format_size(candidate.size_original if candidate else None),
        "availability": availability,
        "last_checked_at": last_checked,
        "item_match": item_match,
        "authenticity": authenticity,
        "listing_utility": listing_utility,
        "evidence_chips": chips,
        "primary_gap": primary_gap,
        "why": why,
    }


def _decision_for(
    controller: CampaignController, search_id: str, candidate_id: str
) -> BucketDecision | None:
    for decision in controller.repos.list_decisions(search_id):
        if decision.candidate_id == candidate_id:
            return decision
    return None


def project_stored_result(
    controller: CampaignController, row: dict[str, Any], *, rank: int
) -> dict[str, Any]:
    search_id = str(row["search_id"])
    result_id = str(row["result_id"])
    candidate_id = str(row["candidate_id"])
    bucket = str(row["public_bucket"])
    candidate = controller.repos.get_candidate(search_id, candidate_id)
    decision = _decision_for(controller, search_id, candidate_id)
    return project_result(
        controller,
        search_id,
        result_id,
        candidate_id=candidate_id,
        bucket=bucket,
        rank=rank,
        decision=decision,
        candidate=candidate,
    )


def list_public_results(
    controller: CampaignController, search_id: str, bucket: str | None
) -> dict[str, Any]:
    public = {
        BucketPublic.REAL.value,
        BucketPublic.POSSIBLY_REAL.value,
        BucketPublic.REPLICA.value,
    }
    rows = [
        row
        for row in controller.repos.list_results(search_id)
        if str(row["public_bucket"]) in public
    ]
    real: list[dict[str, Any]] = []
    possible: list[dict[str, Any]] = []
    replica: list[dict[str, Any]] = []
    targets = {
        BucketPublic.REAL.value: real,
        BucketPublic.POSSIBLY_REAL.value: possible,
        BucketPublic.REPLICA.value: replica,
    }
    for row in rows:
        target = targets[str(row["public_bucket"])]
        target.append(project_stored_result(controller, row, rank=len(target) + 1))
    counts = result_counts(controller, search_id)
    if bucket in {
        BucketPublic.REAL.value,
        BucketPublic.POSSIBLY_REAL.value,
        BucketPublic.REPLICA.value,
    }:
        chosen = targets[bucket]
        return {"search_id": search_id, "bucket": bucket, "results": chosen}
    body: dict[str, Any] = {
        "search_id": search_id,
        "real": real,
        "possibly_real": possible,
        "counts": counts,
    }
    if replica:
        body["replica"] = replica
    return body


def _as_text_map(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in payload.items()}


def project_sse_data(controller: CampaignController, event: CampaignEvent) -> dict[str, Any]:
    payload = strip_private(_as_text_map(event.payload))
    name = event.event_name
    if name == PublicEventName.SEARCH_STATE.value:
        return {
            "state": payload.get("state") or "",
            "version": event.state_version,
        }
    if name == PublicEventName.SEARCH_PROGRESS.value:
        stage = payload.get("stage") or payload.get("phase")
        return {"stage": stage, "detail": payload.get("detail")}
    if name == PublicEventName.SEARCH_COVERAGE.value:
        return _as_coverage(payload)
    if name in {
        PublicEventName.CANDIDATE_DISCOVERED.value,
        PublicEventName.CANDIDATE_NORMALIZED.value,
        PublicEventName.CANDIDATE_PROMOTED.value,
        PublicEventName.CANDIDATE_UPDATED.value,
    }:
        return {"candidate_id": payload.get("candidate_id") or payload.get("url") or ""}
    if name in {
        PublicEventName.RESULT_REAL.value,
        PublicEventName.RESULT_POSSIBLY_REAL.value,
        PublicEventName.RESULT_REPLICA.value,
    }:
        result_id = payload.get("result_id")
        if isinstance(result_id, str) and result_id:
            row = controller.repos.get_result_row(result_id)
            if row is not None and not controller.repos.is_deleted(str(row["search_id"])):
                return project_stored_result(controller, row, rank=1)
        return payload
    if name == PublicEventName.RESULT_REMOVED.value:
        return {
            "result_id": payload.get("result_id") or "",
            "reason": payload.get("reason") or "hidden",
        }
    if name == PublicEventName.SEARCH_WARNING.value:
        return {
            "code": payload.get("code") or "warning",
            "message": payload.get("message") or payload.get("reason") or "",
        }
    if name == PublicEventName.SEARCH_COMPLETE.value:
        terminal = payload.get("terminal_status")
        reason = payload.get("reason") or payload.get("terminal_reason")
        if not terminal:
            campaign = controller.get(event.search_id)
            terminal = campaign.terminal_status.value if campaign.terminal_status else None
            reason = reason or campaign.terminal_reason
        return {"terminal_status": terminal, "reason": reason}
    return payload


def campaign_is_closed(controller: CampaignController, search_id: str) -> bool:
    if controller.repos.is_deleted(search_id):
        return True
    try:
        campaign = controller.repos.get_campaign(search_id)
    except (TypeError, ValueError):
        # A concurrent writer can invalidate a sqlite3.Row mid-read.
        # Do not treat that as terminal; the next poll retries.
        return False
    if campaign is None:
        return True
    return is_terminal(campaign.state)
