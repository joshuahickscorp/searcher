"""Hash-chained receipts. Verification is recomputation."""

from __future__ import annotations

from searcher.receipts.base import ReceiptBase, verify_payload
from searcher.receipts.types import (
    AuthenticityDecisionReceipt,
    BucketDecisionReceipt,
    CampaignTerminalReceipt,
    ComparisonArtifactReceipt,
    CostReceipt,
    FetchRuntimeReceipt,
    HypothesisUpdateReceipt,
    MatchEvidenceReceipt,
    QueryPlanReceipt,
    ReferenceAnalysisReceipt,
    ReferenceIngestionReceipt,
    SearchExhaustionReceipt,
    SourceAdmissionReceipt,
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
    "FetchRuntimeReceipt",
    "ReceiptBase",
    "ReferenceAnalysisReceipt",
    "ReferenceIngestionReceipt",
    "SearchExhaustionReceipt",
    "SourceAdmissionReceipt",
    "SourceRunReceipt",
    "verify_payload",
]
