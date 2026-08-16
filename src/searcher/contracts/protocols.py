"""Adapter protocols. Wave 1 defines the surface; later waves implement it."""

from __future__ import annotations

from typing import Protocol

from searcher.contracts.models import (
    FetchResult,
    ItemHypothesis,
    ListingCandidate,
    MatchEvidence,
    NextEvidenceRequest,
    SourcePlan,
)
from searcher.contracts.primitives import ArtifactRef
from searcher.core.capabilities import CapabilityName, CapabilityRecord


class ReferenceAnalysis(Protocol):
    hypotheses: list[ItemHypothesis]


class VisionCapabilities(Protocol):
    def get(self, name: CapabilityName) -> CapabilityRecord: ...


class NormalizedCandidate(Protocol):
    candidate: ListingCandidate


class RetrievalScore(Protocol):
    candidate_id: str
    score: float


class VerificationResult(Protocol):
    ok: bool
    reason: str


class VisionMCPAdapter(Protocol):
    def capabilities(self) -> VisionCapabilities: ...

    async def analyze_reference_set(
        self,
        images: list[ArtifactRef],
        text: str | None,
        tags: list[str],
    ) -> ReferenceAnalysis: ...

    async def retrieve_candidates(
        self,
        reference: ReferenceAnalysis,
        candidate_images: list[ArtifactRef],
    ) -> list[RetrievalScore]: ...

    async def compare_candidate(
        self,
        reference: ReferenceAnalysis,
        candidate: NormalizedCandidate,
    ) -> MatchEvidence: ...

    async def request_missing_evidence(
        self,
        reference: ReferenceAnalysis,
        leading_candidates: list[NormalizedCandidate],
    ) -> list[NextEvidenceRequest]: ...

    async def verify_receipt(self, receipt: ArtifactRef) -> VerificationResult: ...


class SourceRunRef(Protocol):
    run_id: str


class DiscoveryBatch(Protocol):
    pages: list[str]


class SourceRunState(Protocol):
    run_id: str
    cursor: str | None


class JobScraperAdapter(Protocol):
    async def start_source_run(self, plan: SourcePlan) -> SourceRunRef: ...

    async def next_discovery_batch(self, run: SourceRunRef) -> DiscoveryBatch: ...

    async def fetch_candidates(self, urls: list[str]) -> list[FetchResult]: ...

    async def resume(self, run: SourceRunRef) -> SourceRunState: ...

    async def cancel(self, run: SourceRunRef) -> None: ...
