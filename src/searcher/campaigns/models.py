"""Campaign-internal models: transition context, tasks, packets, snapshots."""

from __future__ import annotations

from pydantic import Field

from searcher.contracts.enums import CampaignState, TaskStatus
from searcher.contracts.models import (
    BucketDecision,
    DiscoveryPage,
    ItemHypothesis,
    ListingCandidate,
    QueryVariant,
)
from searcher.contracts.primitives import SearcherModel
from searcher.core.errors import ErrorClass
from searcher.core.time import UtcDateTime, utc_now
from searcher.evidence.records import EvidenceRecord


class TransitionContext(SearcherModel):
    """Facts the §10.2 guards inspect."""

    has_query: bool = False
    has_visual_representation: bool = False
    normalized_candidate_count: int = 0
    has_visual_or_normalized_evidence: bool = False
    seller_text_only: bool = False
    exhaustion_receipt: str | None = None
    saturation_receipt: str | None = None
    error_class: ErrorClass | None = None
    reason: str = ""
    live_checked_candidates: list[str] = Field(default_factory=list)
    hard_vetoes: dict[str, list[str]] = Field(default_factory=dict)


class Checkpoint(SearcherModel):
    checkpoint_id: str
    search_id: str
    state: CampaignState
    state_version: int
    label: str
    created_at: UtcDateTime = Field(default_factory=utc_now)
    receipt_ref: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class WorkCapsule(SearcherModel):
    task_id: str
    search_id: str
    task_type: str
    input_digests: list[str] = Field(default_factory=list)
    adapter_version: str = "fixture-1"
    backend_version: str = "none"
    policy_version: str
    parameters: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str
    timeout_seconds: int = 30


class EvidencePacket(SearcherModel):
    """Immutable worker return. Only the controller commits it."""

    task_id: str
    search_id: str
    idempotency_key: str
    output_digests: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    outputs: dict[str, object] = Field(default_factory=dict)
    error_class: ErrorClass | None = None
    error: str | None = None


class TaskRecord(SearcherModel):
    task_id: str
    search_id: str
    task_type: str
    idempotency_key: str
    status: TaskStatus
    input_digests: list[str] = Field(default_factory=list)
    output_digests: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class ResumeSnapshot(SearcherModel):
    """§15.6 reconstruction."""

    search_id: str
    state: CampaignState
    state_version: int
    active_hypotheses: list[ItemHypothesis] = Field(default_factory=list)
    completed_queries: list[QueryVariant] = Field(default_factory=list)
    source_cursors: dict[str, str] = Field(default_factory=dict)
    fetched_pages: list[DiscoveryPage] = Field(default_factory=list)
    normalized_candidates: list[ListingCandidate] = Field(default_factory=list)
    pending_comparisons: list[str] = Field(default_factory=list)
    budget_used: dict[str, object] = Field(default_factory=dict)
    result_state: list[BucketDecision] = Field(default_factory=list)
    last_checkpoint: Checkpoint | None = None
    accepted_evidence_ids: list[str] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
