"""Hash-chained receipts. Verification is recomputation."""

from __future__ import annotations

from searcher.receipts.base import ReceiptBase, verify_payload
from searcher.receipts.types import (
    AuthenticityDecisionReceipt,
    BucketDecisionReceipt,
    CampaignTerminalReceipt,
    ComparisonArtifactReceipt,
    CostReceipt,
    HypothesisUpdateReceipt,
    MatchEvidenceReceipt,
    QueryPlanReceipt,
    ReferenceAnalysisReceipt,
    ReferenceIngestionReceipt,
    SearchExhaustionReceipt,
    SourceRunReceipt,
)

__all__ = [
    "AuthenticityDecisionReceipt",
    "BucketDecisionReceipt",
    "CampaignTerminalReceipt",
    "ComparisonArtifactReceipt",
    "CostReceipt",
    "HypothesisUpdateReceipt",
    "MatchEvidenceReceipt",
    "QueryPlanReceipt",
    "ReceiptBase",
    "ReferenceAnalysisReceipt",
    "ReferenceIngestionReceipt",
    "SearchExhaustionReceipt",
    "SourceRunReceipt",
    "verify_payload",
]
