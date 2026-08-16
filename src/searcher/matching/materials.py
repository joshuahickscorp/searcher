"""Material / colour consistency. Uncertainty-aware; never a leather verdict."""

from __future__ import annotations

from searcher.contracts.enums import EvidencePolarity, FactClass
from searcher.contracts.primitives import ScoreWithEvidence
from searcher.matching.scores import make_interval
from searcher.matching.structure import colour_distance
from searcher.matching.types import StructuredDescriptor


def colour_consistency(
    reference: StructuredDescriptor,
    candidate: StructuredDescriptor,
    *,
    exact_colour_required: bool,
) -> tuple[float, list[str], list[str]]:
    """Return (score, contradictions, missing)."""
    dist = colour_distance(reference.dominant_rgb, candidate.dominant_rgb)
    score = max(0.0, 1.0 - dist * 3.2)
    contradictions: list[str] = []
    missing: list[str] = []
    if dist > 0.07 and exact_colour_required:
        contradictions.append("colourway-mismatch")
        score = min(score, 0.25)
    elif dist > 0.12:
        contradictions.append("colour-soft-difference")
        score = min(score, 0.45)
    return score, contradictions, missing


def material_interval(
    reference: StructuredDescriptor,
    candidate: StructuredDescriptor,
    *,
    exact_colour_required: bool,
) -> ScoreWithEvidence:
    score, contra, missing = colour_consistency(
        reference, candidate, exact_colour_required=exact_colour_required
    )
    polarity = EvidencePolarity.CONTRADICTORY if contra else EvidencePolarity.SUPPORTING
    return ScoreWithEvidence(
        interval=make_interval(score, spread=0.1 if not contra else 0.18),
        support=[] if contra else ["ev:colour:hist"],
        contradictions=contra,
        missing=missing,
        fact_class=FactClass.INFERRED,
        polarity=polarity,
    )
