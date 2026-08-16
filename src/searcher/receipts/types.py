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


class MatchEvidenceReceipt(ReceiptBase):
    receipt_type: str = "MatchEvidenceReceipt"
    candidate_id: str = ""
    hypothesis_id: str = ""
    item_match_lower_bound: float = 0.0


class AuthenticityDecisionReceipt(ReceiptBase):
    receipt_type: str = "AuthenticityDecisionReceipt"
    candidate_id: str = ""
    authority_ceiling: str = "uncalibrated"
    public_label: str = "INCOMPLETE EVIDENCE"


class CostReceipt(ReceiptBase):
    receipt_type: str = "CostReceipt"
    stages: list[str] = []
    cache_hits: int = 0
    model_calls: int = 0
    bytes_touched: int = 0
    dedup_savings: int = 0
    cheap_first: bool = False


class ComparisonArtifactReceipt(ReceiptBase):
    receipt_type: str = "ComparisonArtifactReceipt"
    candidate_id: str = ""
    digest: str = ""


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
        "MatchEvidenceReceipt": MatchEvidenceReceipt,
        "AuthenticityDecisionReceipt": AuthenticityDecisionReceipt,
        "CostReceipt": CostReceipt,
        "ComparisonArtifactReceipt": ComparisonArtifactReceipt,
        "ReceiptBase": ReceiptBase,
    }
    cls = mapping.get(str(payload.get("receipt_type", "ReceiptBase")), ReceiptBase)
    return cls.model_validate(payload)
