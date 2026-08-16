"""Photo-set integrity: one item, no unexplained stock insertion."""

from __future__ import annotations

from searcher.contracts.primitives import ScoreWithEvidence
from searcher.matching.cross_image import cross_view_consistency
from searcher.matching.scores import scored
from searcher.matching.types import StructuredDescriptor


def assess_photo_set(
    descriptors: list[StructuredDescriptor],
    *,
    stock_mixed: bool = False,
) -> tuple[ScoreWithEvidence, list[str], list[str]]:
    score, contra, missing = cross_view_consistency(descriptors)
    if stock_mixed:
        contra = list(contra) + ["inserted-stock-photograph"]
        score = min(score, 0.4)
    hard = [c for c in contra if "incompatible" in c]
    return scored(score, spread=0.1, contradictions=contra, missing=missing), hard, missing
