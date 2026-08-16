"""Score containers stay typed; the three judgments do not merge."""

from __future__ import annotations

from searcher.contracts.enums import JudgmentKind
from searcher.contracts.primitives import (
    AuthenticityJudgment,
    ItemMatchJudgment,
    ListingUtilityJudgment,
    ScoreInterval,
)
from searcher.matching.combine import ITEM_WEIGHTS, combine_item_match
from searcher.matching.scores import scored


def test_judgments_remain_distinct() -> None:
    interval = ScoreInterval(mean=0.5, lower_bound=0.4, upper_bound=0.6)
    assert ItemMatchJudgment(interval=interval).kind is JudgmentKind.ITEM_MATCH
    assert AuthenticityJudgment(interval=interval).kind is JudgmentKind.AUTHENTICITY_CONFIDENCE
    assert ListingUtilityJudgment(interval=interval).kind is JudgmentKind.LISTING_UTILITY


def test_item_weights_match_bible_baseline() -> None:
    assert abs(sum(ITEM_WEIGHTS.values()) - 1.0) < 1e-9
    assert ITEM_WEIGHTS["parts"] == 0.30
    assert ITEM_WEIGHTS["text"] == 0.18


def test_hard_contradiction_crushes_item_interval() -> None:
    good = scored(0.95, spread=0.04)
    interval = combine_item_match(
        text=good,
        global_visual=good,
        parts_mean=0.95,
        geometry=good,
        material=good,
        cross=good,
        hard_count=2,
        missing_count=0,
    )
    assert interval.lower_bound <= 0.12
    assert interval.mean <= 0.22
