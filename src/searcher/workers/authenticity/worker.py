"""Authenticity worker. Independent of the item-match worker."""

from __future__ import annotations

from searcher.authenticity.engine import assess_authenticity
from searcher.contracts.models import AuthenticityEvidence, ItemHypothesis, SearchConstraints
from searcher.matching.types import EnrichedCandidate, StructuredDescriptor
from searcher.retrieval.cost import CostLedger


def run_authenticity_worker(
    *,
    hypothesis: ItemHypothesis,
    candidate: EnrichedCandidate,
    reference_descriptors: dict[str, StructuredDescriptor],
    constraints: SearchConstraints | None = None,
    stolen_photo: bool = False,
    ledger: CostLedger | None = None,
) -> AuthenticityEvidence:
    return assess_authenticity(
        hypothesis=hypothesis,
        candidate=candidate,
        reference_descriptors=reference_descriptors,
        constraints=constraints,
        stolen_photo=stolen_photo,
        ledger=ledger,
        deep=True,
    )
