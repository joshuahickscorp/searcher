"""§21 within-tab ranking. Weights are a baseline to beat, not authored truth."""

from __future__ import annotations

from dataclasses import dataclass

from searcher.contracts.enums import BucketPublic
from searcher.contracts.models import BucketDecision, ListingUtility


@dataclass(frozen=True, slots=True)
class RankingWeights:
    item_match: float = 0.34
    authenticity: float = 0.26
    completeness: float = 0.16
    live: float = 0.10
    size_fit: float = 0.06
    image_quality: float = 0.05
    price_fit: float = 0.03


@dataclass
class RankedResult:
    decision: BucketDecision
    utility: ListingUtility | None
    sort_key: tuple[float, ...]
    diversity_key: str


def real_sort_key(
    decision: BucketDecision,
    utility: ListingUtility | None,
    weights: RankingWeights,
) -> tuple[float, ...]:
    live = 1.0 if utility and utility.live else 0.0
    size = (utility.size_match or 0.0) if utility else 0.0
    quality = (utility.image_coverage or 0.0) if utility else 0.0
    price = (utility.price_fit or 0.0) if utility else 0.0
    # Price is last and low-weight. It cannot change the bucket.
    return (
        decision.item_match_lower_bound,
        decision.authenticity_lower_bound,
        decision.evidence_completeness,
        live,
        size,
        quality,
        price * weights.price_fit,
    )


def possibly_sort_key(
    decision: BucketDecision,
    utility: ListingUtility | None,
    missing_resolvable: float,
) -> tuple[float, ...]:
    live = 1.0 if utility and utility.live else 0.0
    quality = (utility.image_coverage or 0.0) if utility else 0.0
    fit = (utility.size_match or 0.0) if utility else 0.0
    return (
        decision.item_match_lower_bound,
        missing_resolvable,
        decision.authenticity_lower_bound,
        live,
        fit,
        quality,
    )


def rank_tab(
    *,
    public: BucketPublic,
    decisions: list[BucketDecision],
    utilities: dict[str, ListingUtility],
    weights: RankingWeights | None = None,
) -> list[RankedResult]:
    w = weights or RankingWeights()
    rows: list[RankedResult] = []
    for decision in decisions:
        if decision.decision.public is not public:
            continue
        utility = utilities.get(decision.candidate_id)
        if public is BucketPublic.REAL:
            key = real_sort_key(decision, utility, w)
        else:
            missing = max(0.0, 1.0 - decision.evidence_completeness)
            key = possibly_sort_key(decision, utility, missing)
        rows.append(
            RankedResult(
                decision=decision,
                utility=utility,
                sort_key=key,
                diversity_key=decision.candidate_id,
            )
        )
    rows.sort(key=lambda row: row.sort_key, reverse=True)
    return rows
