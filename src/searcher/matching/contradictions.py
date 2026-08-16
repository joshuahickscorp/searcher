"""Hard vs soft item-match contradictions (§18.5, §19.4 for the match side)."""

from __future__ import annotations

from searcher.matching.types import GeometryResult, StructuredDescriptor


def item_contradictions(
    *,
    reference: StructuredDescriptor,
    candidate: StructuredDescriptor,
    geometry: GeometryResult,
    exact_colour_required: bool,
    colour_hard: bool,
    label_hash_mismatch: bool,
    apply_footwear_rules: bool = True,
) -> tuple[list[str], list[str]]:
    hard: list[str] = []
    soft: list[str] = []
    if apply_footwear_rules:
        if geometry.eyelet_delta >= 2:
            hard.append("eyelet-count-mismatch")
        elif geometry.eyelet_delta == 1:
            soft.append("eyelet-count-soft")
        if geometry.panel_delta >= 1:
            hard.append("panel-count-mismatch")
        if abs(reference.outsole_ratio - candidate.outsole_ratio) >= 0.07:
            hard.append("outsole-geometry-mismatch")
        elif abs(reference.outsole_ratio - candidate.outsole_ratio) >= 0.04:
            soft.append("outsole-geometry-soft")
        if geometry.heel_angle_delta >= 0.25 or (
            reference.heel_cut != candidate.heel_cut
            and {reference.heel_cut, candidate.heel_cut} <= {"block", "rounded", "notched"}
            and "unknown" not in {reference.heel_cut, candidate.heel_cut}
        ):
            # Adjacent block vs notched/rounded is a construction change.
            if reference.heel_cut != candidate.heel_cut:
                hard.append("heel-construction-mismatch")
            else:
                soft.append("heel-angle-soft")
        if (
            reference.logo_kind
            and candidate.logo_kind
            and reference.logo_kind != candidate.logo_kind
        ):
            soft.append("logo-kind-soft")
        if reference.logo_xy and candidate.logo_xy:
            from searcher.matching.structure import logo_distance

            if logo_distance(reference.logo_xy, candidate.logo_xy) >= 0.18:
                hard.append("logo-placement-mismatch")
        if label_hash_mismatch:
            hard.append("label-code-mismatch")
    if exact_colour_required and colour_hard:
        hard.append("colourway-hard-mismatch")
    return hard, soft
