"""§21.3 item-match combination. Three judgments stay independent."""

from __future__ import annotations

from searcher.contracts.primitives import PartMatch, ScoreInterval, ScoreWithEvidence
from searcher.matching.scores import apply_hard_penalty, clamp01, make_interval, weighted_mean

ITEM_WEIGHTS = {
    "text": 0.18,
    "global": 0.18,
    "parts": 0.30,
    "geometry": 0.16,
    "material": 0.08,
    "cross": 0.10,
}


def combine_item_match(
    *,
    text: ScoreWithEvidence,
    global_visual: ScoreWithEvidence,
    parts_mean: float,
    geometry: ScoreWithEvidence,
    material: ScoreWithEvidence,
    cross: ScoreWithEvidence,
    hard_count: int,
    missing_count: int,
) -> ScoreInterval:
    mean = weighted_mean(
        [
            (ITEM_WEIGHTS["text"], text.interval.mean),
            (ITEM_WEIGHTS["global"], global_visual.interval.mean),
            (ITEM_WEIGHTS["parts"], parts_mean),
            (ITEM_WEIGHTS["geometry"], geometry.interval.mean),
            (ITEM_WEIGHTS["material"], material.interval.mean),
            (ITEM_WEIGHTS["cross"], cross.interval.mean),
        ]
    )
    lower_src = weighted_mean(
        [
            (ITEM_WEIGHTS["text"], text.interval.lower_bound),
            (ITEM_WEIGHTS["global"], global_visual.interval.lower_bound),
            (ITEM_WEIGHTS["parts"], max(0.0, parts_mean - 0.06)),
            (ITEM_WEIGHTS["geometry"], geometry.interval.lower_bound),
            (ITEM_WEIGHTS["material"], material.interval.lower_bound),
            (ITEM_WEIGHTS["cross"], cross.interval.lower_bound),
        ]
    )
    spread = 0.04 + 0.03 * min(4, missing_count)
    lower = clamp01(min(mean, lower_src) - spread * 0.15)
    upper = clamp01(max(mean, 0.55) + 0.04)
    interval = ScoreInterval(
        mean=round(clamp01(mean), 6),
        lower_bound=round(min(lower, mean), 6),
        upper_bound=round(max(upper, mean), 6),
    )
    correspondence_backed = any("correspondence" in item for item in geometry.support)
    if hard_count:
        interval = apply_hard_penalty(interval, hard_count=hard_count)
    elif (
        parts_mean >= 0.9
        and geometry.interval.mean >= 0.9
        and (global_visual.interval.mean >= 0.88 or correspondence_backed)
        and missing_count <= 2
    ):
        # Strong visual identity: tighten the published lower bound.
        # Correspondence, not the embedding, is the identity evidence. The
        # embedding's median on genuine pairs is ~0.81, so requiring global
        # >= 0.88 treated a shortlist cut as a gate the term cannot pass.
        lifted = min(interval.mean, max(interval.lower_bound, 0.91))
        interval = ScoreInterval(
            mean=interval.mean,
            lower_bound=round(lifted, 6),
            upper_bound=interval.upper_bound,
        )
    return interval


def part_matches_mean(parts: list[PartMatch]) -> float:
    if not parts:
        return 0.4
    return sum(item.interval.mean for item in parts) / len(parts)


def empty_scored(mean: float = 0.45) -> ScoreWithEvidence:
    from searcher.matching.scores import scored

    return scored(mean, spread=0.16, missing=["component"])


def tight(mean: float, *, support: list[str] | None = None) -> ScoreWithEvidence:
    from searcher.matching.scores import scored

    return scored(mean, spread=0.05, support=support or [])


def make_part_match(
    name: str,
    mean: float,
    *,
    explanation: str | None = None,
    correspondence_ref: str | None = None,
) -> PartMatch:
    return PartMatch(
        part_name=name,
        interval=make_interval(mean, spread=0.07),
        explanation=explanation,
        correspondence_ref=correspondence_ref,
    )
