"""Colour contradiction is collected across considered pairs, not the winner."""

from __future__ import annotations

import pytest
from tests.helpers_matching import constraints, make_candidate, make_hypothesis, views_for

from searcher.contracts.enums import ImageRole
from searcher.matching.materials import colour_consistency as real_colour_consistency
from searcher.matching.perturb import (
    brightness,
    colour_temperature,
    jpeg,
    mild_crop,
    mild_rotate,
    screenshot_frame,
)
from searcher.matching.pipeline import (
    _capped_view_pairs,
    enrich_candidate,
    match_candidate,
    prepare_reference,
)
from searcher.matching.synth import COLOURWAY_SHOE, REFERENCE_SHOE, render_views


def _score(*, images, reference_pngs, colour: str | None = "olive"):
    listing, cand_pngs = make_candidate(
        images=images,
        title="House Name Field Model 07",
    )
    hyp = make_hypothesis()
    evidence = match_candidate(
        hypothesis=hyp,
        candidate=enrich_candidate(listing, cand_pngs, category="footwear"),
        reference_pngs=reference_pngs,
        reference_descriptors=prepare_reference(reference_pngs),
        constraints=constraints(colour=colour),
    )
    return evidence


def _colourway_with_flattering_extra() -> list[tuple[str, bytes, ImageRole]]:
    """Canonical red colourway plus the extras that let best-of-N hide it.

    `lateral_cool` is still the wrong item. Pairing prefers it because the
    desaturated lateral is closer to the olive reference; the red lateral
    still contradicts.
    """
    images = views_for(COLOURWAY_SHOE)
    by_name = {name: (png, role) for name, png, role in images}
    png, role = by_name["lateral"]
    extras: list[tuple[str, bytes, ImageRole]] = [
        ("lateral_jpeg", jpeg(png, 72), role),
        ("lateral_crop", mild_crop(png, 8), role),
        ("lateral_bright", brightness(png, 1.18), role),
        ("lateral_cool", colour_temperature(png, 0.65), role),
        ("lateral_phone", screenshot_frame(png), role),
        ("lateral_tilt", mild_rotate(png, 4.0), role),
    ]
    front = by_name.get("front")
    if front is not None:
        extras.append(("front_jpeg", jpeg(front[0], 68), front[1]))
        extras.append(("front_crop", mild_crop(front[0], 10), front[1]))
    sole = by_name.get("sole")
    if sole is not None:
        extras.append(("sole_crop", mild_crop(sole[0], 6), sole[1]))
    heel = by_name.get("heel")
    if heel is not None:
        extras.append(("heel_jpeg", jpeg(heel[0], 70), heel[1]))
    return images + extras


def test_flattering_pair_does_not_erase_colourway_contradiction() -> None:
    ref = render_views(REFERENCE_SHOE)
    one = _score(images=[views_for(COLOURWAY_SHOE)[0]], reference_pngs=ref)
    many = _score(images=_colourway_with_flattering_extra(), reference_pngs=ref)

    assert one.item_match_distribution.lower_bound < 0.45
    assert "colourway-hard-mismatch" in one.hard_contradictions
    assert many.item_match_distribution.lower_bound < 0.45
    assert "colourway-hard-mismatch" in many.hard_contradictions
    assert "colourway-mismatch" in many.material.contradictions


def test_true_match_does_not_accumulate_label_as_colourway() -> None:
    ref = render_views(REFERENCE_SHOE)
    evidence = _score(images=views_for(REFERENCE_SHOE), reference_pngs=ref)

    assert "colourway-hard-mismatch" not in evidence.hard_contradictions
    assert "colourway-mismatch" not in evidence.material.contradictions
    assert evidence.item_match_distribution.lower_bound >= 0.90


def test_authentic_poor_photos_do_not_move() -> None:
    ref = render_views(REFERENCE_SHOE)
    poor = [("lateral", jpeg(views_for(REFERENCE_SHOE)[0][1], 55), ImageRole.PRODUCT)]
    evidence = _score(images=poor, reference_pngs=ref)

    assert "colourway-hard-mismatch" not in evidence.hard_contradictions
    assert evidence.item_match_distribution.lower_bound >= 0.75


def test_adding_views_to_a_true_item_does_not_lower_item_match() -> None:
    ref_all = render_views(REFERENCE_SHOE)
    views = views_for(REFERENCE_SHOE)
    one = _score(images=[views[0]], reference_pngs={"lateral": ref_all["lateral"]})
    five = _score(images=views, reference_pngs=ref_all)

    assert five.item_match_distribution.lower_bound >= one.item_match_distribution.lower_bound


def test_colour_is_evaluated_on_considered_pairs_not_only_the_winner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str]] = []

    def _capture(ref_desc, cand_desc, *, exact_colour_required):
        seen.append((ref_desc.image_id, cand_desc.image_id))
        return real_colour_consistency(
            ref_desc, cand_desc, exact_colour_required=exact_colour_required
        )

    monkeypatch.setattr("searcher.matching.pipeline.colour_consistency", _capture)
    _score(images=_colourway_with_flattering_extra(), reference_pngs=render_views(REFERENCE_SHOE))

    assert seen
    laterals = [cand_id for _ref_id, cand_id in seen if "lateral" in cand_id]
    assert laterals
    contradicting = [
        cand_id
        for cand_id in laterals
        if "cool" not in cand_id and "label" not in cand_id
    ]
    assert contradicting, f"expected a non-cool lateral among colour pairs, got {seen}"


def test_pair_budget_stays_at_nine() -> None:
    ref = render_views(REFERENCE_SHOE)
    listing, cand_pngs = make_candidate(
        images=_colourway_with_flattering_extra(),
        title="House Name Field Model 07",
    )
    enriched = enrich_candidate(listing, cand_pngs, category="footwear")
    considered = _capped_view_pairs(
        ref,
        enriched.pngs,
        prepare_reference(ref),
        enriched.descriptors,
        footwear=True,
    )
    assert len(considered) <= 9
    assert len(considered) == 9
