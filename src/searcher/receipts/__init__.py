"""Hash-chained receipts. Verification is recomputation."""

from __future__ import annotations

from searcher.receipts.base import ReceiptBase, verify_payload
from searcher.receipts.types import (
    BucketDecisionReceipt,
    CampaignTerminalReceipt,
    FetchRuntimeReceipt,
    ReferenceIngestionReceipt,
    SearchExhaustionReceipt,
    SourceAdmissionReceipt,
    SourceRunReceipt,
)

__all__ = [
    "BucketDecisionReceipt",
    "CampaignTerminalReceipt",
    "FetchRuntimeReceipt",
    "ReceiptBase",
    "ReferenceIngestionReceipt",
    "SearchExhaustionReceipt",
    "SourceAdmissionReceipt",
    "SourceRunReceipt",
    "verify_payload",
]
