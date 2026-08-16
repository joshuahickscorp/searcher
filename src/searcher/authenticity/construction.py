"""Construction consistency against the authenticity reference, not item ID."""

from __future__ import annotations

from searcher.authenticity.profiles.base import CategoryProfile
from searcher.contracts.primitives import ScoreWithEvidence
from searcher.matching.scores import scored
from searcher.matching.types import StructuredDescriptor


def assess_construction(
    *,
    profile: CategoryProfile,
    reference: StructuredDescriptor | None,
    candidate: StructuredDescriptor | None,
) -> tuple[ScoreWithEvidence, list[str], list[str]]:
    hard: list[str] = []
    soft: list[str] = []
    if "panel_count" not in profile.construction_checks:
        return scored(0.5, spread=0.2, missing=["construction-profile"]), hard, soft
    if reference is None or candidate is None:
        return scored(0.45, spread=0.25, missing=["construction-view"]), hard, soft
    penalties = 0.0
    if abs(reference.eyelet_count - candidate.eyelet_count) >= 2:
        hard.append("construction-eyelet-count")
        penalties += 0.35
    if abs(reference.panel_count - candidate.panel_count) >= 1:
        hard.append("construction-panel-count")
        penalties += 0.3
    if abs(reference.outsole_ratio - candidate.outsole_ratio) >= 0.07:
        hard.append("construction-outsole")
        penalties += 0.2
    if reference.heel_cut != candidate.heel_cut and {reference.heel_cut, candidate.heel_cut} <= {
        "block",
        "rounded",
        "notched",
    }:
        hard.append("construction-heel")
        penalties += 0.2
    mean = max(0.08, 0.9 - penalties)
    return scored(mean, spread=0.07 if not hard else 0.16, contradictions=hard), hard, soft
