"""A wrong item with many views must not clear the plausible floor."""

from __future__ import annotations

from benchmark.corpus import (
    NEGATIVE_PARENTS,
    build_cases,
    build_view_restricted,
    hypothesis_for,
    images_for,
    multiview_case_id,
    one_view,
    reference_pngs,
)
from benchmark.splits import BUCKET_TRUTH, HELD_OUT_BUCKET_IDS, assign_splits, hardneg_item_id

from searcher.matching.pipeline import enrich_candidate, match_candidate, prepare_reference
from searcher.ranking.policy_versions import load_policy


def _plausible_floor() -> float:
    return float(load_policy("matching-1").possibly.plausible_item_match_lower_bound)


def _item_match_lower(case_id: str, *, n_views: int | None) -> float:
    case = build_view_restricted(case_id, BUCKET_TRUTH, n_views=n_views)
    hyp, cons = hypothesis_for([case])
    ref = reference_pngs()
    if n_views == 1:
        lateral = next(iter(ref.values()))
        ref = {"lateral": lateral}
    enriched = enrich_candidate(case.candidate, case.pngs, category=hyp.category)
    evidence = match_candidate(
        hypothesis=hyp,
        candidate=enriched,
        reference_pngs=ref,
        reference_descriptors=prepare_reference(ref),
        constraints=cons,
    )
    return float(evidence.item_match_distribution.lower_bound)


def test_multiview_variants_are_labelled_and_have_more_photographs() -> None:
    splits = assign_splits()
    for parent in sorted(NEGATIVE_PARENTS):
        child = multiview_case_id(parent)
        assert child in BUCKET_TRUTH
        assert BUCKET_TRUTH[child] == BUCKET_TRUTH[parent]
        parent_images = images_for(parent)
        child_images = images_for(child)
        assert len(parent_images) >= 1
        assert len(child_images) > len(parent_images)
        assert [name for name, _png, _role in child_images[: len(parent_images)]] == [
            name for name, _png, _role in parent_images
        ]
        parent_item = splits.item(hardneg_item_id(parent))
        child_item = splits.item(hardneg_item_id(child))
        assert parent_item.truth_bucket == child_item.truth_bucket
        assert parent_item.split == child_item.split
        if parent in HELD_OUT_BUCKET_IDS:
            assert child in HELD_OUT_BUCKET_IDS


def test_one_view_helper_keeps_only_the_first_photograph() -> None:
    images = images_for("adjacent_model")
    assert len(images) > 1
    clipped = one_view(images)
    assert len(clipped) == 1
    assert clipped[0][0] == images[0][0]


# Structural hard-negatives: extra photographs stay the same wrong item, so
# construction / replica / label mismatches still fire. Colourway is different
# — a cooler-lit extra lateral can drop the colour hard contradiction.
_STRUCTURAL_MULTIVIEW = (
    "adjacent_model_multiview",
    "replica_copied_title_multiview",
    "copied_product_code_multiview",
    "counterfeit_excellent_photos_multiview",
    "ai_generated_multiview",
)


def test_wrong_item_with_many_views_stays_below_plausible_floor() -> None:
    floor = _plausible_floor()
    assert floor == 0.45
    cases = build_cases(list(_STRUCTURAL_MULTIVIEW), BUCKET_TRUTH)
    assert {case.case_id for case in cases} == set(_STRUCTURAL_MULTIVIEW)
    over: list[str] = []
    for case_id in _STRUCTURAL_MULTIVIEW:
        lower = _item_match_lower(case_id, n_views=None)
        if lower >= floor:
            over.append(f"{case_id}={lower:.6f}")
    assert over == [], (
        "best-of-N pairing lifted a wrong item to or above the plausible floor "
        f"{floor}: {', '.join(over)}"
    )


def test_colourway_multiview_crosses_plausible_floor() -> None:
    """Named finding: extra photographs of a different colourway clear 0.45.

    A cooler-lit lateral of the red colourway is still the wrong item. Pairing
    prefers it over the canonical red lateral, the colour hard contradiction
    drops, and the item-match lower bound jumps from the hard-penalty floor
    to the true-match band. Routing may still hide the listing via the
    authenticity colour veto; the item-match number itself does not.
    """
    floor = _plausible_floor()
    one = _item_match_lower("different_colourway", n_views=1)
    many = _item_match_lower("different_colourway_multiview", n_views=None)
    assert one < floor, f"1-view colourway should sit below {floor}, got {one}"
    assert many >= floor, (
        f"expected different_colourway_multiview to cross {floor}, got {many}"
    )


def test_ai_generated_five_views_cross_plausible_floor() -> None:
    """Existing 5-view negative, not a new fixture: pairing already inflates it."""
    floor = _plausible_floor()
    one = _item_match_lower("ai_generated", n_views=1)
    five = _item_match_lower("ai_generated", n_views=None)
    assert one < floor
    assert five >= floor
