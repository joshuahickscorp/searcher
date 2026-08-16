"""§18.5 geometric and relational consistency."""

from __future__ import annotations

from searcher.matching.structure import logo_distance
from searcher.matching.types import GeometryResult, StructuredDescriptor


def compare_geometry(
    reference: StructuredDescriptor,
    candidate: StructuredDescriptor,
) -> GeometryResult:
    eyelet_delta = abs(reference.eyelet_count - candidate.eyelet_count)
    panel_delta = abs(reference.panel_count - candidate.panel_count)
    outsole_delta = abs(reference.outsole_ratio - candidate.outsole_ratio)
    sole_delta = abs(reference.sole_to_upper - candidate.sole_to_upper)
    heel_angle_delta = abs(reference.heel_angle - candidate.heel_angle)
    aspect_delta = abs(reference.aspect - candidate.aspect)
    heel_cut_mismatch = reference.heel_cut != candidate.heel_cut and {
        reference.heel_cut,
        candidate.heel_cut,
    } <= {"block", "rounded", "notched"}
    logo_d = logo_distance(reference.logo_xy, candidate.logo_xy)
    notes: list[str] = []
    score = 1.0
    if eyelet_delta:
        score -= min(0.35, 0.12 * eyelet_delta)
        notes.append(f"eyelet_delta={eyelet_delta}")
    if panel_delta:
        score -= min(0.3, 0.14 * panel_delta)
        notes.append(f"panel_delta={panel_delta}")
    if outsole_delta > 0.04:
        score -= min(0.2, outsole_delta)
        notes.append(f"outsole_delta={outsole_delta:.3f}")
    if sole_delta > 0.08:
        score -= 0.08
    if heel_angle_delta > 0.15 or heel_cut_mismatch:
        score -= 0.12
        notes.append(f"heel={reference.heel_cut}->{candidate.heel_cut}")
    if aspect_delta > 0.25:
        score -= 0.08
    if logo_d > 0.18:
        score -= min(0.16, logo_d)
        notes.append(f"logo_shift={logo_d:.3f}")
    if reference.tread_kind != candidate.tread_kind and "unknown" not in {
        reference.tread_kind,
        candidate.tread_kind,
    }:
        score -= 0.1
        notes.append(f"tread={reference.tread_kind}->{candidate.tread_kind}")
    return GeometryResult(
        score=max(0.0, min(1.0, score)),
        sole_to_upper_delta=round(sole_delta, 4),
        heel_angle_delta=round(heel_angle_delta, 4),
        aspect_delta=round(aspect_delta, 4),
        panel_delta=panel_delta,
        eyelet_delta=eyelet_delta,
        notes=notes,
    )
