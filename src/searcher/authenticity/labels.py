"""Product-code and label checks. Low-resolution text is not overclaimed."""

from __future__ import annotations

import re

from searcher.contracts.primitives import ScoreWithEvidence
from searcher.matching.scores import scored
from searcher.matching.types import StructuredDescriptor
from searcher.reference.injection import looks_like_instruction

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{3,}$")


def assess_labels(
    *,
    reference: StructuredDescriptor | None,
    candidate: StructuredDescriptor | None,
    listing_text: str | None,
    reference_code: str | None,
) -> tuple[ScoreWithEvidence, list[str], list[str]]:
    hard: list[str] = []
    missing: list[str] = []
    if listing_text and looks_like_instruction(listing_text):
        # Data only. Do not treat as a code or as an authenticity instruction.
        listing_text = None
    if candidate is None or not candidate.label_hash:
        missing.append("label-view")
        return scored(0.42, spread=0.22, missing=missing), hard, missing
    if reference is None or not reference.label_hash:
        missing.append("reference-label")
        return scored(0.48, spread=0.2, missing=missing), hard, missing
    if candidate.label_hash != reference.label_hash:
        hard.append("label-code-incompatible")
        return scored(0.18, spread=0.12, contradictions=hard), hard, missing
    if reference_code and not _CODE.match(reference_code):
        missing.append("code-format-uncertain")
    return scored(0.82, spread=0.08, support=["ev:label:hash"]), hard, missing
