"""§30.1 receipt types relevant to wave 1."""

from __future__ import annotations

from typing import Any

from searcher.receipts.base import ReceiptBase


class ReferenceIngestionReceipt(ReceiptBase):
    receipt_type: str = "ReferenceIngestionReceipt"
    reference_image_ids: list[str] = []
    byte_count: int = 0


class ReferenceAnalysisReceipt(ReceiptBase):
    receipt_type: str = "ReferenceAnalysisReceipt"
    analysis_id: str = ""
    crop_count: int = 0
    ocr_count: int = 0
    cluster_count: int = 0
    donor_invoked: bool = False
    promotion_blocked: bool = False
    blocked_lanes: list[str] = []


class HypothesisUpdateReceipt(ReceiptBase):
    receipt_type: str = "HypothesisUpdateReceipt"
    hypothesis_ids: list[str] = []
    active_count: int = 0
    archived_count: int = 0
    contradiction_count: int = 0


class QueryPlanReceipt(ReceiptBase):
    receipt_type: str = "QueryPlanReceipt"
    query_ids: list[str] = []
    languages: list[str] = []
    families: list[str] = []
    max_round: int = 0
    query_count: int = 0


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


class FeedbackReceipt(ReceiptBase):
    receipt_type: str = "FeedbackReceipt"
    result_id: str = ""
    verdict: str = ""


class DeletionReceipt(ReceiptBase):
    receipt_type: str = "DeletionReceipt"
    removed: list[str] = []
    retained: list[str] = []


class LiveCheckReceipt(ReceiptBase):
    receipt_type: str = "LiveCheckReceipt"
    result_ids: list[str] = []
    refreshed: bool = False
    reason: str = ""


def typed_from_payload(payload: dict[str, Any]) -> ReceiptBase:
    mapping: dict[str, type[ReceiptBase]] = {
        "ReferenceIngestionReceipt": ReferenceIngestionReceipt,
        "ReferenceAnalysisReceipt": ReferenceAnalysisReceipt,
        "HypothesisUpdateReceipt": HypothesisUpdateReceipt,
        "QueryPlanReceipt": QueryPlanReceipt,
        "SourceRunReceipt": SourceRunReceipt,
        "BucketDecisionReceipt": BucketDecisionReceipt,
        "SearchExhaustionReceipt": SearchExhaustionReceipt,
        "CampaignTerminalReceipt": CampaignTerminalReceipt,
        "FeedbackReceipt": FeedbackReceipt,
        "DeletionReceipt": DeletionReceipt,
        "LiveCheckReceipt": LiveCheckReceipt,
        "ReceiptBase": ReceiptBase,
    }
    cls = mapping.get(str(payload.get("receipt_type", "ReceiptBase")), ReceiptBase)
    return cls.model_validate(payload)
