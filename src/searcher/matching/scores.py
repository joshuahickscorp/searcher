"""Interval helpers used by matching and authenticity. Not a blended score."""

from __future__ import annotations

from searcher.contracts.enums import EvidencePolarity, FactClass
from searcher.contracts.primitives import ScoreInterval, ScoreWithEvidence


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def make_interval(mean: float, *, spread: float) -> ScoreInterval:
    mid = clamp01(mean)
    width = max(0.0, float(spread))
    lower = clamp01(mid - width)
    upper = clamp01(mid + width * 0.55)
    if lower > mid:
        lower = mid
    if upper < mid:
        upper = mid
    return ScoreInterval(
        mean=round(mid, 6),
        lower_bound=round(lower, 6),
        upper_bound=round(upper, 6),
    )


def scored(
    mean: float,
    *,
    spread: float = 0.08,
    support: list[str] | None = None,
    contradictions: list[str] | None = None,
    missing: list[str] | None = None,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORTING,
    fact_class: FactClass = FactClass.INFERRED,
) -> ScoreWithEvidence:
    return ScoreWithEvidence(
        interval=make_interval(mean, spread=spread),
        support=list(support or []),
        contradictions=list(contradictions or []),
        missing=list(missing or []),
        fact_class=fact_class,
        polarity=polarity,
    )


def missing_score(*what: str) -> ScoreWithEvidence:
    return scored(
        0.45,
        spread=0.28,
        missing=list(what),
        polarity=EvidencePolarity.MISSING,
    )


def weighted_mean(pairs: list[tuple[float, float]]) -> float:
    total_w = sum(weight for weight, _value in pairs)
    if total_w <= 0:
        return 0.0
    return sum(weight * value for weight, value in pairs) / total_w


def apply_hard_penalty(interval: ScoreInterval, *, hard_count: int) -> ScoreInterval:
    if hard_count <= 0:
        return interval
    mean = min(interval.mean, 0.22)
    lower = min(interval.lower_bound, 0.12)
    upper = min(interval.upper_bound, max(mean, 0.35))
    if lower > mean:
        lower = mean
    if upper < mean:
        upper = mean
    return ScoreInterval(mean=mean, lower_bound=lower, upper_bound=upper)
