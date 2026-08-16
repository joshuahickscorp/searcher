"""Broad-retrieval entry used by the vision worker."""

from __future__ import annotations

from searcher.contracts.models import ItemHypothesis, ListingCandidate, VisualSignature
from searcher.retrieval.broad import BroadRetrievalResult, retrieve_broad
from searcher.retrieval.cost import CostLedger
from searcher.retrieval.escalation import EscalationBounds


def run_broad_retrieval(
    *,
    candidates: list[ListingCandidate],
    hypothesis: ItemHypothesis,
    reference_signature: VisualSignature,
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, dict[str, bytes]],
    candidate_ocr: dict[str, list[str]] | None = None,
    ledger: CostLedger | None = None,
    bounds: EscalationBounds | None = None,
    already_deduplicated: bool = False,
) -> BroadRetrievalResult:
    return retrieve_broad(
        candidates=candidates,
        hypothesis=hypothesis,
        reference_signature=reference_signature,
        reference_pngs=reference_pngs,
        candidate_pngs=candidate_pngs,
        candidate_ocr=candidate_ocr,
        ledger=ledger,
        bounds=bounds,
        already_deduplicated=already_deduplicated,
    )
