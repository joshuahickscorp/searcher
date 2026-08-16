"""§32.4 sensitivity: structural change must move the measurement."""

from __future__ import annotations

from searcher.matching.perturb import render_variant, structural_variant
from searcher.matching.structure import extract_structure, logo_distance
from searcher.matching.synth import REFERENCE_SHOE, render_shoe


def test_sensitivity_matrix() -> None:
    ref_png = render_shoe(REFERENCE_SHOE, view="lateral")
    ref = extract_structure(ref_png, image_id="ref")
    # Label sensitivity uses the label view.
    ref_label = extract_structure(render_shoe(REFERENCE_SHOE, view="label"), image_id="rl")

    def lateral(kind: str):
        png = render_variant(REFERENCE_SHOE, kind, view="lateral")
        return extract_structure(png, image_id=kind)

    panels = lateral("panel-count")
    assert panels.panel_count != ref.panel_count

    eyelets = lateral("eyelet-count")
    assert eyelets.eyelet_count != ref.eyelet_count

    outsole = lateral("outsole")
    assert abs(outsole.outsole_ratio - ref.outsole_ratio) >= 0.04

    logo = lateral("logo")
    assert logo_distance(ref.logo_xy, logo.logo_xy) >= 0.12

    heel = lateral("heel")
    assert heel.heel_cut != ref.heel_cut or abs(heel.heel_angle - ref.heel_angle) >= 0.1

    colour = lateral("colourway")
    from searcher.matching.structure import colour_distance

    assert colour_distance(ref.dominant_rgb, colour.dominant_rgb) >= 0.04

    label = extract_structure(
        render_shoe(structural_variant(REFERENCE_SHOE, "label"), view="label"),
        image_id="lab",
    )
    assert label.label_hash != ref_label.label_hash
