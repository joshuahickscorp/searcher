"""Hash-chained receipts. Verification is recomputation."""

from __future__ import annotations

from searcher.receipts.base import ReceiptBase, verify_payload
from searcher.receipts.types import (
    BucketDecisionReceipt,
    CampaignTerminalReceipt,
    DeletionReceipt,
    FeedbackReceipt,
    HypothesisUpdateReceipt,
    LiveCheckReceipt,
    QueryPlanReceipt,
    ReferenceAnalysisReceipt,
    ReferenceIngestionReceipt,
    SearchExhaustionReceipt,
    SourceRunReceipt,
)

__all__ = [
    "BucketDecisionReceipt",
    "CampaignTerminalReceipt",
    "DeletionReceipt",
    "FeedbackReceipt",
    "HypothesisUpdateReceipt",
    "LiveCheckReceipt",
    "QueryPlanReceipt",
    "ReceiptBase",
    "ReferenceAnalysisReceipt",
    "ReferenceIngestionReceipt",
    "SearchExhaustionReceipt",
    "SourceRunReceipt",
    "verify_payload",
]
