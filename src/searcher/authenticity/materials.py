"""Material inference remains uncertainty-aware."""

from __future__ import annotations

from searcher.contracts.primitives import ScoreWithEvidence
from searcher.matching.scores import scored
from searcher.matching.structure import colour_distance
from searcher.matching.types import StructuredDescriptor


def assess_materials(
    *,
    reference: StructuredDescriptor | None,
    candidate: StructuredDescriptor | None,
    exact_colour_required: bool,
) -> tuple[ScoreWithEvidence, list[str], list[str]]:
    hard: list[str] = []
    soft: list[str] = []
    if reference is None or candidate is None:
        return scored(0.45, spread=0.22, missing=["material-view"]), hard, ["material-view"]
    dist = colour_distance(reference.dominant_rgb, candidate.dominant_rgb)
    # Smoothness gap is a weak material/photo cue, never a leather claim.
    smooth_delta = abs(reference.smoothness - candidate.smoothness)
    mean = max(0.15, 0.85 - dist * 2.8 - smooth_delta * 0.3)
    if exact_colour_required and dist > 0.07:
        hard.append("material-colourway")
        mean = min(mean, 0.25)
    elif dist > 0.12:
        soft.append("material-colour-soft")
    return scored(mean, spread=0.12, contradictions=hard + soft), hard, []
