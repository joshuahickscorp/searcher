"""Logo / typography consistency. Placement and kind only; no brand verdict."""

from __future__ import annotations

from searcher.contracts.primitives import ScoreWithEvidence
from searcher.matching.scores import scored
from searcher.matching.structure import logo_distance
from searcher.matching.types import StructuredDescriptor


def assess_logos(
    *,
    reference: StructuredDescriptor | None,
    candidate: StructuredDescriptor | None,
) -> tuple[ScoreWithEvidence, list[str], list[str]]:
    hard: list[str] = []
    missing: list[str] = []
    if reference is None or candidate is None:
        missing.append("logo-view")
        return scored(0.45, spread=0.2, missing=missing), hard, missing
    if reference.logo_xy is None or candidate.logo_xy is None:
        missing.append("logo-not-resolved")
        return scored(0.48, spread=0.18, missing=missing), hard, missing
    dist = logo_distance(reference.logo_xy, candidate.logo_xy)
    kind_mismatch = (
        reference.logo_kind and candidate.logo_kind and reference.logo_kind != candidate.logo_kind
    )
    if dist >= 0.18 or kind_mismatch:
        hard.append("logo-incompatible")
        return scored(0.2, spread=0.12, contradictions=hard), hard, missing
    return scored(0.84, spread=0.08, support=["ev:logo:placement"]), hard, missing
