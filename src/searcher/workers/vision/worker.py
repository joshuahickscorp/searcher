"""Vision worker capsule. Idempotent; returns immutable packets."""

from __future__ import annotations

from searcher.authenticity.photo_reuse import screen_photo_reuse
from searcher.contracts.models import ItemHypothesis, ListingCandidate, SearchConstraints
from searcher.core.ids import idempotency_key
from searcher.ranking.pipeline import JudgmentReport, judge_candidates
from searcher.retrieval.escalation import EscalationBounds


def _embed_batch(
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, dict[str, bytes]],
) -> None:
    """One forward pass for every candidate/reference image the judge will see."""
    try:
        from searcher.retrieval.embeddings import embed_pngs, resolve_backend
    except Exception:
        return
    backend = resolve_backend()
    if backend is None:
        return
    blobs: list[bytes] = list(reference_pngs.values())
    for group in candidate_pngs.values():
        blobs.extend(group.values())
    if blobs:
        embed_pngs(blobs, backend)


def run_vision_worker(
    *,
    search_id: str,
    hypothesis: ItemHypothesis,
    candidates: list[ListingCandidate],
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, dict[str, bytes]],
    constraints: SearchConstraints | None = None,
    already_deduplicated: bool = True,
    destination_verified: dict[str, bool] | None = None,
    stolen: set[str] | None = None,
    stock_mixed: set[str] | None = None,
    policy_version: str = "matching-1",
    bounds: EscalationBounds | None = None,
) -> JudgmentReport:
    from searcher.ranking.policy_versions import load_policy

    _embed_batch(reference_pngs, candidate_pngs)
    key = idempotency_key(
        task_type="vision_match",
        search_id=search_id,
        input_digests=sorted(reference_pngs),
        adapter_version="searcher-matching-1",
        backend_version="classical",
        policy_version=policy_version,
        parameters={"n": len(candidates)},
    )
    del key
    # Screen the photographs rather than waiting to be told about them. Until
    # this ran, `stolen` was only ever supplied by tests, so the theft veto was
    # unreachable in production and the Real gate stayed fail-closed for every
    # candidate. A caller may still pass its own findings; this fills the gap
    # when it does not, so screening has genuinely happened either way.
    screened_reuse, screened_stock = screen_photo_reuse(candidates)
    return judge_candidates(
        search_id=search_id,
        hypothesis=hypothesis,
        candidates=candidates,
        reference_pngs=reference_pngs,
        candidate_pngs=candidate_pngs,
        constraints=constraints,
        already_deduplicated=already_deduplicated,
        destination_verified=destination_verified,
        stolen=stolen if stolen is not None else screened_reuse,
        stock_mixed=stock_mixed if stock_mixed is not None else screened_stock,
        policy=load_policy(policy_version),
        bounds=bounds,
    )
