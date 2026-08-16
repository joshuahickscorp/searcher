"""Immutable evidence records with lineage back to input digests."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from searcher.contracts.enums import EvidencePolarity, FactClass
from searcher.contracts.primitives import SearcherModel
from searcher.core.time import UtcDateTime
from searcher.evidence.lineage import Lineage


class EvidenceRecord(SearcherModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    evidence_id: str
    search_id: str
    content_digest: str
    family_id: str
    polarity: EvidencePolarity
    fact_class: FactClass
    accepted: bool
    lineage: Lineage
    created_at: UtcDateTime
    label: str = ""
    hard: bool = False
    notes: list[str] = Field(default_factory=list)
    private: bool = True
