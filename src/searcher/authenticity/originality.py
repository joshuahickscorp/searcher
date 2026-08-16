"""Image originality. Duplicate families do not increase independence."""

from __future__ import annotations

from searcher.contracts.primitives import ScoreWithEvidence
from searcher.evidence.independence import independent_family_count
from searcher.evidence.records import EvidenceRecord
from searcher.matching.scores import scored


def assess_originality(
    *,
    image_records: list[EvidenceRecord],
    stolen_photo: bool,
    known_stock_hit: bool,
) -> tuple[ScoreWithEvidence, list[str], list[str]]:
    hard: list[str] = []
    families = independent_family_count(image_records) if image_records else 1
    mean = 0.7 if families >= 1 else 0.45
    if stolen_photo or known_stock_hit:
        hard.append("image-theft-or-rehost")
        mean = 0.12
    support = ["ev:originality:families"]
    return scored(mean, spread=0.1, contradictions=hard, support=support), hard, []
