"""Consult the warm index before source work; remember public listings after."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import Availability, PublicEventName
from searcher.contracts.models import (
    AuthenticityEvidence,
    ListingCandidate,
    ListingUtility,
    MatchEvidence,
    SearchConstraints,
)
from searcher.core.ids import new_id
from searcher.index.keys import CacheVersions, versions_from_settings
from searcher.index.liveness import apply_liveness_ttl, liveness_expired
from searcher.index.store import (
    IndexHit,
    WarmIndex,
    descriptor_from_bytes,
    hypothesis_digest,
    parse_listing,
)
from searcher.index.text import query_terms
from searcher.index.vectors import hashed_text_vector
from searcher.ranking.buckets import route_candidate
from searcher.receipts.types import CostReceipt


@dataclass
class ConsultResult:
    surfaced: int = 0
    cache_hits: int = 0
    ior_skipped: int = 0
    skip_source_work: bool = False
    candidate_ids: list[str] = field(default_factory=list)
    routed: int = 0


def _index(controller: CampaignController) -> WarmIndex:
    return WarmIndex(controller.repos)


def _versions(controller: CampaignController) -> CacheVersions:
    return versions_from_settings(controller.settings)


def consult_and_surface(controller: CampaignController, search_id: str) -> ConsultResult:
    """Surface stored public listings that match this campaign's hypothesis."""
    settings = controller.settings
    result = ConsultResult()
    if not settings.index_enabled:
        return result
    index = _index(controller)
    versions = _versions(controller)
    intent = controller.repos.get_intent(search_id)
    hypotheses = controller.repos.list_hypotheses(search_id)
    terms = query_terms(intent, hypotheses)
    if not terms:
        return result
    query_vec = hashed_text_vector(terms)
    hits = index.search(terms, versions, query_descriptor=query_vec)
    if not hits:
        _write_cost(
            controller,
            search_id,
            phase="consult",
            cache_hits=0,
            fetches=len(controller.repos.list_fetch_attempts(search_id)),
            extra={"listings_surfaced": 0, "ior_skipped": 0},
        )
        return result
    ior_skipped = 0
    for query in controller.repos.list_queries(search_id):
        sources = {hit.source_adapter for hit in hits if hit.source_adapter}
        for source_id in sources:
            if index.query_already_run(
                source_id=source_id, query_text=query.query_text, versions=versions
            ):
                ior_skipped += 1
    primary = max(hypotheses, key=lambda item: item.posterior) if hypotheses else None
    digest = hypothesis_digest(primary) if primary is not None else ""
    existing_urls = {item.canonical_url for item in controller.repos.list_candidates(search_id)}
    for hit in hits:
        if hit.canonical_url in existing_urls:
            continue
        candidate = _hydrate(hit, search_id, ttl_seconds=settings.liveness_ttl_seconds)
        controller.repos.upsert_candidate(search_id, candidate)
        existing_urls.add(candidate.canonical_url)
        result.candidate_ids.append(candidate.candidate_id)
        result.surfaced += 1
        result.cache_hits += 1
        controller.emit(
            search_id,
            PublicEventName.CANDIDATE_DISCOVERED.value,
            payload={
                "url": candidate.canonical_url,
                "from_index": True,
                "last_checked_at": candidate.last_checked_at.isoformat(),
            },
            actor="index",
        )
        controller.emit(
            search_id,
            PublicEventName.CANDIDATE_NORMALIZED.value,
            payload={"candidate_id": candidate.candidate_id, "from_index": True},
            actor="index",
        )
        if digest:
            routed = _replay_evidence(
                controller,
                search_id,
                index=index,
                hit=hit,
                candidate=candidate,
                hypothesis_digest=digest,
                versions=versions,
            )
            if routed:
                result.routed += 1
    result.ior_skipped = ior_skipped
    result.skip_source_work = bool(hits) and ior_skipped > 0
    runtime = controller.repos.get_runtime(search_id)
    coverage = runtime.get("coverage")
    if not isinstance(coverage, dict):
        coverage = {}
    coverage = dict(coverage)
    coverage["candidates_normalized"] = (
        int(coverage.get("candidates_normalized") or 0) + result.surfaced
    )
    controller.set_runtime(
        search_id,
        index_hits=result.surfaced,
        index_skip_source_work=result.skip_source_work,
        index_ior_skipped=ior_skipped,
        index_routed=result.routed,
        coverage=coverage,
    )
    _write_cost(
        controller,
        search_id,
        phase="consult",
        cache_hits=result.cache_hits,
        fetches=len(controller.repos.list_fetch_attempts(search_id)),
        extra={
            "listings_surfaced": result.surfaced,
            "ior_skipped": ior_skipped,
            "routed": result.routed,
        },
    )
    return result


def remember_campaign(controller: CampaignController, search_id: str) -> int:
    """Persist public listing work so the next overlapping search starts warm."""
    settings = controller.settings
    if not settings.index_enabled:
        return 0
    index = _index(controller)
    versions = _versions(controller)
    stored = 0
    scores = controller.repos.list_scores(search_id)
    decisions = {item.candidate_id: item for item in controller.repos.list_decisions(search_id)}
    hypotheses = controller.repos.list_hypotheses(search_id)
    primary = max(hypotheses, key=lambda item: item.posterior) if hypotheses else None
    digest = hypothesis_digest(primary) if primary is not None else ""
    for candidate in controller.repos.list_candidates(search_id):
        descriptors: dict[str, list[float]] = {}
        for image in candidate.images:
            if not image.content_digest:
                continue
            data = _listing_bytes(controller, search_id, image.content_digest)
            if data is None:
                continue
            vector = descriptor_from_bytes(data)
            if vector is not None:
                descriptors[image.content_digest] = vector
        listing_key = index.put_listing(candidate, versions, descriptors=descriptors)
        stored += 1
        if digest:
            match_row, auth_row = _score_pair(scores, candidate.candidate_id)
            if match_row is not None and auth_row is not None:
                decision = decisions.get(candidate.candidate_id)
                match_payload = _payload_obj(match_row)
                auth_payload = _payload_obj(auth_row)
                index.put_evidence(
                    listing_key=listing_key,
                    hypothesis_digest=digest,
                    versions=versions,
                    item_match_mean=float(match_row["mean"]),
                    item_match_lower=float(match_row["lower_bound"]),
                    item_match_upper=float(match_row["upper_bound"]),
                    authenticity_mean=float(auth_row["mean"]),
                    authenticity_lower=float(auth_row["lower_bound"]),
                    authenticity_upper=float(auth_row["upper_bound"]),
                    completeness=float(decision.evidence_completeness) if decision else 0.4,
                    destination_verified=True,
                    hard_vetoes=list(decision.hard_vetoes) if decision else [],
                    match_payload=match_payload,
                    authenticity_payload=auth_payload,
                )
    for query in controller.repos.list_queries(search_id):
        for run in controller.repos.list_source_runs(search_id):
            source_id = str(run.get("source_id") or "")
            if not source_id:
                continue
            index.record_query(
                source_id=source_id,
                query_text=query.query_text,
                versions=versions,
                pages=1,
            )
    fetches = len(controller.repos.list_fetch_attempts(search_id))
    _write_cost(
        controller,
        search_id,
        phase="remember",
        cache_hits=0,
        fetches=fetches,
        extra={"listings_remembered": stored},
    )
    return stored


def _hydrate(hit: IndexHit, search_id: str, *, ttl_seconds: int) -> ListingCandidate:
    del search_id
    raw = dict(hit.payload)
    raw["candidate_id"] = new_id()
    images = []
    for image in raw.get("images") or []:
        if not isinstance(image, dict):
            continue
        copied = dict(image)
        copied["listing_image_id"] = new_id()
        copied["candidate_id"] = raw["candidate_id"]
        images.append(copied)
    raw["images"] = images
    candidate = parse_listing(raw)
    # last_checked_at is preserved from the stored payload; TTL only changes presentation.
    return apply_liveness_ttl(candidate, ttl_seconds=ttl_seconds)


def _replay_evidence(
    controller: CampaignController,
    search_id: str,
    *,
    index: WarmIndex,
    hit: IndexHit,
    candidate: ListingCandidate,
    hypothesis_digest: str,
    versions: CacheVersions,
) -> bool:
    evidence = index.get_evidence(hit.listing_key, hypothesis_digest, versions)
    if evidence is None or evidence.match_payload is None or evidence.authenticity_payload is None:
        return False
    match = MatchEvidence.model_validate(evidence.match_payload)
    auth = AuthenticityEvidence.model_validate(evidence.authenticity_payload)
    # Copy intervals exactly. Never raise a stored lower bound.
    match = match.model_copy(
        update={
            "match_evidence_id": new_id(),
            "candidate_id": candidate.candidate_id,
            "item_match_distribution": match.item_match_distribution,
        }
    )
    auth = auth.model_copy(
        update={
            "authenticity_evidence_id": new_id(),
            "candidate_id": candidate.candidate_id,
            "authenticity_distribution": auth.authenticity_distribution,
        }
    )
    if match.item_match_distribution.lower_bound > evidence.item_match_lower:
        return False
    if auth.authenticity_distribution.lower_bound > evidence.authenticity_lower:
        return False
    ttl = controller.settings.liveness_ttl_seconds
    expired = liveness_expired(candidate.last_checked_at, ttl_seconds=ttl)
    live_now = candidate.availability is Availability.LIVE and not expired
    utility = ListingUtility(
        live=live_now,
        last_checked_at=candidate.last_checked_at,
        utility_score=1.0 if live_now else 0.0,
        image_coverage=min(1.0, len(candidate.images) / 4.0),
        description_quality=0.5,
    )
    controller.repos.insert_score(
        search_id,
        match.match_evidence_id,
        "ITEM_MATCH",
        match.item_match_distribution.mean,
        match.item_match_distribution.lower_bound,
        match.item_match_distribution.upper_bound,
        match.model_dump(mode="json"),
        candidate_id=candidate.candidate_id,
    )
    controller.repos.insert_score(
        search_id,
        auth.authenticity_evidence_id,
        "AUTHENTICITY_CONFIDENCE",
        auth.authenticity_distribution.mean,
        auth.authenticity_distribution.lower_bound,
        auth.authenticity_distribution.upper_bound,
        auth.model_dump(mode="json"),
        candidate_id=candidate.candidate_id,
    )
    decision = route_candidate(
        candidate=candidate,
        match=match,
        authenticity=auth,
        utility=utility,
        completeness_value=evidence.completeness,
        constraints=SearchConstraints(),
        destination_verified=evidence.destination_verified and live_now,
        live_checked=live_now,
    )
    controller.repos.insert_decision(search_id, new_id(), decision)
    result_id = new_id()
    controller.repos.insert_result(
        search_id,
        result_id,
        candidate.candidate_id,
        decision.decision.public.value,
        decision.model_dump(mode="json"),
    )
    public = decision.decision.public.value
    if public == "real":
        name = PublicEventName.RESULT_REAL.value
    elif public == "possibly_real":
        name = PublicEventName.RESULT_POSSIBLY_REAL.value
    else:
        name = PublicEventName.RESULT_REMOVED.value
    controller.emit(
        search_id,
        name,
        payload={
            "candidate_id": candidate.candidate_id,
            "result_id": result_id,
            "from_index": True,
            "last_checked_at": candidate.last_checked_at.isoformat(),
        },
        actor="index",
    )
    return True


def _score_pair(
    scores: list[dict[str, Any]], candidate_id: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    match: dict[str, Any] | None = None
    auth: dict[str, Any] | None = None
    for row in scores:
        if str(row.get("candidate_id") or "") != candidate_id:
            continue
        payload = str(row.get("payload_json") or "")
        if row["kind"] == "ITEM_MATCH" and "match_evidence_id" in payload:
            match = row
        elif row["kind"] == "AUTHENTICITY_CONFIDENCE":
            auth = row
    return match, auth


def _payload_obj(row: dict[str, Any]) -> dict[str, Any] | None:
    raw = row.get("payload_json")
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    import json

    data = json.loads(str(raw))
    return data if isinstance(data, dict) else None


def _listing_bytes(controller: CampaignController, search_id: str, digest: str) -> bytes | None:
    try:
        return controller.store.get(digest, campaign_id=search_id)
    except Exception:
        try:
            return controller.store.get(digest)
        except Exception:
            return None


def _write_cost(
    controller: CampaignController,
    search_id: str,
    *,
    phase: str,
    cache_hits: int,
    fetches: int,
    extra: dict[str, Any],
) -> None:
    receipt = CostReceipt(
        search_id=search_id,
        stages=["cache"] if cache_hits else ["hashes_and_metadata"],
        cache_hits=cache_hits,
        payload={"phase": phase, "fetches": fetches, **extra},
    ).seal()
    controller.store_receipt(receipt)


def hydrate_from_index(
    controller: CampaignController,
    search_id: str,
    hit: IndexHit,
) -> ListingCandidate:
    return _hydrate(hit, search_id, ttl_seconds=controller.settings.liveness_ttl_seconds)
