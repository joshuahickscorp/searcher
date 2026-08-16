"""Vision worker capsule. Idempotent; returns immutable packets."""

from __future__ import annotations

from searcher.contracts.models import ItemHypothesis, ListingCandidate, SearchConstraints
from searcher.core.ids import idempotency_key
from searcher.ranking.pipeline import JudgmentReport, judge_candidates
from searcher.retrieval.escalation import EscalationBounds


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
    policy_version: str = "matching-1",
    bounds: EscalationBounds | None = None,
) -> JudgmentReport:
    from searcher.ranking.policy_versions import load_policy

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
    return judge_candidates(
        search_id=search_id,
        hypothesis=hypothesis,
        candidates=candidates,
        reference_pngs=reference_pngs,
        candidate_pngs=candidate_pngs,
        constraints=constraints,
        already_deduplicated=already_deduplicated,
        destination_verified=destination_verified,
        stolen=stolen,
        policy=load_policy(policy_version),
        bounds=bounds,
    )
