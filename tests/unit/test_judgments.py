"""The three judgments stay independently typed."""

from __future__ import annotations

from searcher.contracts.enums import JudgmentKind
from searcher.contracts.primitives import (
    AuthenticityJudgment,
    ItemMatchJudgment,
    ListingUtilityJudgment,
    ScoreInterval,
    as_authenticity,
    as_item_match,
    as_listing_utility,
)


def test_kinds_are_distinct() -> None:
    interval = ScoreInterval(mean=0.5, lower_bound=0.4, upper_bound=0.6)
    item = ItemMatchJudgment(interval=interval)
    auth = AuthenticityJudgment(interval=interval)
    util = ListingUtilityJudgment(interval=interval, live=True)
    assert item.kind is JudgmentKind.ITEM_MATCH
    assert auth.kind is JudgmentKind.AUTHENTICITY_CONFIDENCE
    assert util.kind is JudgmentKind.LISTING_UTILITY
    assert as_item_match(item).kind is JudgmentKind.ITEM_MATCH
    assert as_authenticity(auth).kind is JudgmentKind.AUTHENTICITY_CONFIDENCE
    assert as_listing_utility(util).kind is JudgmentKind.LISTING_UTILITY
    assert type(item) is not type(auth)
    assert type(auth) is not type(util)
