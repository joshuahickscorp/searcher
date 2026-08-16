"""§26.6 VisionMCP adapter. Donor types never leak past schema_map."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from searcher.contracts.models import (
    NextEvidenceRequest,
    ReferenceAnalysis,
)
from searcher.contracts.primitives import ArtifactRef
from searcher.core.capabilities import CapabilityName, CapabilityRecord, CapabilityReport
from searcher.core.config import Settings
from searcher.core.errors import CapabilityUnavailable
from searcher.core.ids import new_id
from searcher.evidence.content_store import ContentStore
from searcher.integrations.visionmcp.compatibility import (
    ADAPTER_VERSION,
    PINNED_SHA,
    PINNED_VERSION,
    assert_imaging_contract,
    import_visionmcp,
    visionmcp_enabled,
)
from searcher.integrations.visionmcp.probe import probe_capabilities
from searcher.integrations.visionmcp.receipts import VerificationResult, verify_searcher_receipt
from searcher.integrations.visionmcp.schema_map import map_inspect_image

# retrieve_candidates and compare_candidate are owned by a later matching wave.
_MATCHING_WAVE = "later matching wave"


class VisionCapabilitiesView:
    def __init__(self, report: CapabilityReport) -> None:
        self._records = {record.name: record for record in report.capabilities}

    def get(self, name: CapabilityName) -> CapabilityRecord:
        return self._records[name]

    def all(self) -> list[CapabilityRecord]:
        return list(self._records.values())


class SearcherVisionAdapter:
    """In-process adapter. Heavy donor imports are lazy and never happen at probe."""

    def __init__(
        self,
        store: ContentStore | None = None,
        *,
        search_id: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.search_id = search_id
        self.settings = settings or Settings.from_env()
        self.adapter_version = ADAPTER_VERSION

    def capabilities(self) -> VisionCapabilitiesView:
        return VisionCapabilitiesView(probe_capabilities())

    def donor_available(self) -> bool:
        return bool(visionmcp_enabled() and import_visionmcp() is not None)

    def inspect_via_donor(self, path: Path) -> dict[str, Any] | None:
        """Real VisionMCP inspect_image call. None if the donor is absent."""
        if not self.donor_available():
            return None
        if self.settings.privacy_mode not in {"local", "balanced", "deep"}:
            return None
        try:
            assert_imaging_contract()
        except Exception:
            return None
        from visionmcp.evidence.references import inspect_image

        metadata, quality = inspect_image(path)
        return map_inspect_image(metadata, quality)

    async def analyze_reference_set(
        self,
        images: list[ArtifactRef],
        text: str | None,
        tags: list[str],
    ) -> ReferenceAnalysis:
        from searcher.reference.analysis import analyze_stored_references

        if self.store is None:
            raise CapabilityUnavailable(
                "IMAGE_DECODE",
                wave="this wave",
                reason="adapter has no content store; cannot load reference bytes",
            )
        return analyze_stored_references(
            self.store,
            images,
            text=text,
            tags=list(tags),
            search_id=self.search_id or new_id(),
            settings=self.settings,
            donor_inspect=self.inspect_via_donor if self.donor_available() else None,
        )

    async def retrieve_candidates(
        self,
        reference: ReferenceAnalysis,
        candidate_images: list[ArtifactRef],
    ) -> list[Any]:
        # Capability not available in this wave. Do not return placeholder scores.
        del reference, candidate_images
        raise CapabilityUnavailable("retrieve_candidates", wave=_MATCHING_WAVE)

    async def compare_candidate(
        self,
        reference: ReferenceAnalysis,
        candidate: Any,
    ) -> Any:
        # Capability not available in this wave. Do not return placeholder scores.
        del reference, candidate
        raise CapabilityUnavailable("compare_candidate", wave=_MATCHING_WAVE)

    async def request_missing_evidence(
        self,
        reference: ReferenceAnalysis,
        leading_candidates: list[Any],
    ) -> list[NextEvidenceRequest]:
        from searcher.reference.gaps import request_missing_evidence

        del leading_candidates
        return request_missing_evidence(reference)

    async def verify_receipt(self, receipt: ArtifactRef | dict[str, Any]) -> VerificationResult:
        if isinstance(receipt, dict):
            return verify_searcher_receipt(receipt)
        if self.store is None:
            raise CapabilityUnavailable(
                "RECEIPT_VERIFY.donor",
                wave="this wave",
                reason="no store to load receipt bytes; donor verify is not imported",
            )
        raw = self.store.get(receipt.digest, campaign_id=self.search_id)
        import json

        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, dict) and payload.get("receipt_type"):
            return verify_searcher_receipt(payload)
        raise CapabilityUnavailable(
            "RECEIPT_VERIFY.donor",
            wave="this wave",
            reason=(
                "not a Searcher receipt; donor verify_any_receipt is unavailable "
                f"(pinned {PINNED_VERSION} @{PINNED_SHA[:12]} imports compiler kernels)"
            ),
        )
