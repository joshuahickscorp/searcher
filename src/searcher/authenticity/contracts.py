"""Internal authenticity types. Public record remains AuthenticityEvidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from searcher.contracts.primitives import ScoreInterval, ScoreWithEvidence


class EvidenceLabel:
    HIGH = "HIGH EVIDENCE"
    MODERATE = "MODERATE EVIDENCE"
    INCOMPLETE = "INCOMPLETE EVIDENCE"
    CONTRADICTORY = "CONTRADICTORY EVIDENCE"


@dataclass
class CategorySignals:
    construction: ScoreWithEvidence
    labels: ScoreWithEvidence
    logos: ScoreWithEvidence
    materials: ScoreWithEvidence
    photo_set: ScoreWithEvidence
    originality: ScoreWithEvidence
    source: ScoreWithEvidence
    provenance: ScoreWithEvidence
    price: ScoreWithEvidence
    hard: list[str] = field(default_factory=list)
    soft: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    completeness: float = 0.0
    calibrated: bool = False
    interval: ScoreInterval | None = None
    public_label: str = EvidenceLabel.INCOMPLETE
    authority_ceiling: str = "uncalibrated"
