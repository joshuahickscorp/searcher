"""A category without its own profile must still be able to be complete.

The generic profile expected a view literally named "unknown", which no listing
can supply. Coverage was therefore always zero and completeness pinned at
0.6*0 + 0.4*1 = 0.4 for every non-footwear item — the authenticity_lower_bound
of 0.4 seen on every published garment. Nothing outside footwear could clear an
authenticity gate above 0.4, so a garment could never reach Real no matter how
well it matched.
"""

from __future__ import annotations

from searcher.authenticity.completeness import completeness
from searcher.authenticity.profiles import profile_for
from searcher.contracts.enums import ViewHypothesis


def test_generic_profile_expects_views_a_listing_can_actually_supply() -> None:
    profile = profile_for("garment")
    vocabulary = {view.value for view in ViewHypothesis}
    assert profile.expected_views, "a profile with no expected views scores zero"
    assert "unknown" not in profile.expected_views
    for view in profile.expected_views:
        assert view in vocabulary, f"{view} is not a view the classifier can emit"


def test_a_fully_photographed_garment_can_reach_full_completeness() -> None:
    profile = profile_for("garment")
    value, missing = completeness(profile=profile, present_views=set(profile.expected_views))
    assert value == 1.0
    assert missing == []


def test_a_garment_with_no_views_is_not_rewarded() -> None:
    profile = profile_for("garment")
    value, missing = completeness(profile=profile, present_views=set())
    assert value < 0.5
    assert missing == list(profile.expected_views)


def test_footwear_keeps_its_own_stricter_profile() -> None:
    profile = profile_for("footwear")
    assert "sole" in profile.expected_views
    assert "sole" in profile.critical_views
