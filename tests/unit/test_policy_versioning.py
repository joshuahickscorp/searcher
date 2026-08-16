"""Policy versions are data. Benchmarks can swap them."""

from __future__ import annotations

from searcher.ranking.policy_versions import available_versions, load_policy, register_policy


def test_matching_and_provisional_are_registered() -> None:
    versions = available_versions()
    assert "matching-1" in versions
    assert "provisional-1" in versions
    matching = load_policy("matching-1")
    provisional = load_policy("provisional-1")
    assert matching.require_calibrated_for_real is True
    assert provisional.require_calibrated_for_real is False
    assert matching.dead_listing_is_hard_veto is True
    assert provisional.dead_listing_is_hard_veto is False
    assert matching.real.item_match_lower_bound == 0.90


def test_register_policy_is_additive() -> None:
    base = load_policy("matching-1")
    clone = type(base)(
        version="matching-1-strict",
        real=base.real,
        possibly=base.possibly,
        ranking=base.ranking,
        require_calibrated_for_real=True,
        dead_listing_is_hard_veto=True,
    )
    register_policy(clone)
    assert load_policy("matching-1-strict").version == "matching-1-strict"
