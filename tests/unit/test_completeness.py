"""Evidence completeness by expected view."""

from __future__ import annotations

from searcher.authenticity.completeness import completeness
from searcher.authenticity.profiles import profile_for


def test_critical_views_raise_completeness() -> None:
    profile = profile_for("footwear")
    low, missing = completeness(profile=profile, present_views={"lateral"})
    high, missing_high = completeness(
        profile=profile, present_views={"lateral", "heel", "sole", "label", "front"}
    )
    assert low < 0.4
    assert high >= 0.65
    assert "medial" in missing
    assert "label" not in missing_high


def test_unknown_category_does_not_use_footwear_views() -> None:
    profile = profile_for("watch")
    value, missing = completeness(profile=profile, present_views={"unknown"})
    assert profile.critical_views == ()
    assert "lateral" not in missing
    assert value >= 0.0
