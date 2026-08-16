"""Combined invariance / sensitivity report used as required evidence."""

from __future__ import annotations

from searcher.matching.perturb import (
    background_change,
    brightness,
    jpeg,
    mild_crop,
    resize,
    structural_variant,
)
from searcher.matching.structure import extract_structure
from searcher.matching.synth import REFERENCE_SHOE, render_shoe


def test_both_directions_are_required() -> None:
    base = render_shoe(REFERENCE_SHOE, view="lateral")
    ref = extract_structure(base, image_id="ref")
    jpeg_d = extract_structure(jpeg(base), image_id="j")
    crop_d = extract_structure(mild_crop(base), image_id="c")
    bright_d = extract_structure(brightness(base), image_id="b")
    bg_d = extract_structure(background_change(base), image_id="bg")
    resize_d = extract_structure(resize(base, 0.85), image_id="z")
    for got in (jpeg_d, crop_d, bright_d, bg_d, resize_d):
        assert abs(got.eyelet_count - ref.eyelet_count) <= 1
        assert abs(got.panel_count - ref.panel_count) <= 1
    changed = extract_structure(
        render_shoe(structural_variant(REFERENCE_SHOE, "panel-count"), view="lateral"),
        image_id="p",
    )
    assert changed.panel_count != ref.panel_count
