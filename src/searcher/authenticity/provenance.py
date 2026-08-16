"""Provenance is weak. Packaging never overrides a physical hard contradiction."""

from __future__ import annotations

from searcher.contracts.models import ListingCandidate
from searcher.contracts.primitives import ScoreWithEvidence
from searcher.matching.scores import scored


def assess_provenance(candidate: ListingCandidate) -> tuple[ScoreWithEvidence, list[str]]:
    text = " ".join(
        str(part.value) for part in (candidate.title, candidate.description) if part and part.value
    ).lower()
    hits = 0
    for token in ("receipt", "box", "dust bag", "dustbag", "invoice"):
        if token in text:
            hits += 1
    if hits == 0:
        return scored(0.4, spread=0.2, missing=["provenance"]), ["provenance"]
    mean = min(0.62, 0.4 + 0.08 * hits)
    return scored(mean, spread=0.16, support=["ev:provenance:mentioned"]), []
