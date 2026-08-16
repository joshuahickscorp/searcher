"""Cheap visual match used after broad retrieval, before part correspondence."""

from __future__ import annotations

from searcher.contracts.primitives import ScoreWithEvidence
from searcher.matching.scores import scored
from searcher.matching.structure import colour_distance
from searcher.matching.types import StructuredDescriptor
from searcher.reference.imaging import average_hash, hamming


def global_visual(
    reference: StructuredDescriptor,
    candidate: StructuredDescriptor,
    *,
    reference_png: bytes,
    candidate_png: bytes,
) -> ScoreWithEvidence:
    rh = average_hash(reference_png)
    ch = average_hash(candidate_png)
    perceptual = max(0.0, 1.0 - hamming(rh, ch) / 64.0)
    colour = max(0.0, 1.0 - colour_distance(reference.dominant_rgb, candidate.dominant_rgb) * 3.0)
    aspect = max(0.0, 1.0 - abs(reference.aspect - candidate.aspect))
    mean = 0.5 * perceptual + 0.3 * colour + 0.2 * aspect
    support = ["ev:global:ahash", "ev:global:colour", "ev:global:aspect"]
    return scored(mean, spread=0.07, support=support)
