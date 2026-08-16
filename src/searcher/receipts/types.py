"""§30.1 receipt types relevant to wave 1."""

from __future__ import annotations

from typing import Any

from searcher.receipts.base import ReceiptBase


class ReferenceIngestionReceipt(ReceiptBase):
    receipt_type: str = "ReferenceIngestionReceipt"
    reference_image_ids: list[str] = []
    byte_count: int = 0


class SourceRunReceipt(ReceiptBase):
    receipt_type: str = "SourceRunReceipt"
    source_id: str = ""
    outcome: str = ""
    pages: int = 0
    matches: int = 0


class BucketDecisionReceipt(ReceiptBase):
    receipt_type: str = "BucketDecisionReceipt"
    candidate_id: str = ""
    internal: str = ""
    public: str = ""
    policy_version: str = "provisional-1"


class SearchExhaustionReceipt(ReceiptBase):
    receipt_type: str = "SearchExhaustionReceipt"
    reason: str = ""
    saturation: bool = False
    queries_exhausted: int = 0
    sources_covered: int = 0


class CampaignTerminalReceipt(ReceiptBase):
    receipt_type: str = "CampaignTerminalReceipt"
    terminal_status: str = ""
    terminal_reason: str = ""
    state_version: int = 0


def typed_from_payload(payload: dict[str, Any]) -> ReceiptBase:
    mapping: dict[str, type[ReceiptBase]] = {
        "ReferenceIngestionReceipt": ReferenceIngestionReceipt,
        "SourceRunReceipt": SourceRunReceipt,
        "BucketDecisionReceipt": BucketDecisionReceipt,
        "SearchExhaustionReceipt": SearchExhaustionReceipt,
        "CampaignTerminalReceipt": CampaignTerminalReceipt,
        "ReceiptBase": ReceiptBase,
    }
    cls = mapping.get(str(payload.get("receipt_type", "ReceiptBase")), ReceiptBase)
    return cls.model_validate(payload)
