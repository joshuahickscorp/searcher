"""Visual similarity used to rank the closed-set gallery.

Prefers the shipped DINOv2 cosine when local weights load. Otherwise uses
the visual half of Searcher's cheap Stage-A signals (average hash + colour
histogram). The receipt names which scorer produced the numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from searcher.reference.imaging import average_hash, colour_histogram, hamming
from searcher.retrieval.embeddings import (
    BACKBONE_IDENTITY,
    OPERATING_THRESHOLD,
    cosine_similarity,
    embed_png,
    resolve_backend,
)


def _hist_l1(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return max(0.0, 1.0 - 0.5 * sum(abs(a - b) for a, b in zip(left, right, strict=True)))


def cheap_visual_similarity(reference: bytes, candidate: bytes) -> float:
    perceptual = max(0.0, 1.0 - hamming(average_hash(reference), average_hash(candidate)) / 64.0)
    colour = _hist_l1(colour_histogram(reference), colour_histogram(candidate))
    return 0.6 * perceptual + 0.4 * colour


@dataclass(frozen=True, slots=True)
class Scorer:
    identity: str
    units: str
    threshold_applies: bool
    notes: str
    backend_identity: str | None = None

    def score(self, reference: bytes, candidate: bytes) -> float:
        raise NotImplementedError

    def as_payload(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "units": self.units,
            "threshold_applies": self.threshold_applies,
            "backend_identity": self.backend_identity,
            "shipped_threshold": OPERATING_THRESHOLD,
            "notes": self.notes,
        }


class _EmbeddingScorer(Scorer):
    def score(self, reference: bytes, candidate: bytes) -> float:
        left = embed_png(reference)
        right = embed_png(candidate)
        if left is None or right is None:
            return cheap_visual_similarity(reference, candidate)
        return cosine_similarity(left, right)


class _CheapScorer(Scorer):
    def score(self, reference: bytes, candidate: bytes) -> float:
        return cheap_visual_similarity(reference, candidate)


def resolve_scorer() -> Scorer:
    backend = resolve_backend()
    if backend is None:
        return _CheapScorer(
            identity="searcher.cheap_visual.ahash_colour",
            units="weighted_perceptual_colour_in_[0,1]",
            threshold_applies=False,
            notes=(
                "No local embedding weights. Ranking uses Searcher's cheap "
                "visual signals (average hash + colour histogram). The shipped "
                f"{OPERATING_THRESHOLD} operating point is a DINOv2 cosine "
                "threshold from artifacts/searcher-match-calibration.receipt.json "
                "and is not a point on this fallback scale."
            ),
        )
    return _EmbeddingScorer(
        identity=BACKBONE_IDENTITY,
        units="cosine",
        threshold_applies=True,
        backend_identity=backend.identity,
        notes=(
            "DINOv2 ViT-S/14 CLS, L2-normalised cosine. Operating threshold "
            f"{OPERATING_THRESHOLD} is the shipped pair gate, not retuned here."
        ),
    )


def embeddings_available() -> bool:
    return resolve_backend() is not None
