"""§5.13 capability registry. Probe implementations land in later waves."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from searcher import SCHEMA_VERSION


class CapabilityName(StrEnum):
    IMAGE_DECODE = "IMAGE_DECODE"
    OBJECT_SEGMENTATION = "OBJECT_SEGMENTATION"
    DENSE_FEATURES = "DENSE_FEATURES"
    OCR = "OCR"
    LOGO_DETECTION = "LOGO_DETECTION"
    LOCAL_CORRESPONDENCE = "LOCAL_CORRESPONDENCE"
    MATERIAL_ANALYSIS = "MATERIAL_ANALYSIS"
    BROWSER_CAPTURE = "BROWSER_CAPTURE"
    WORLD_STATE = "WORLD_STATE"
    NEXT_VIEW = "NEXT_VIEW"
    RECEIPT_VERIFY = "RECEIPT_VERIFY"


class CapabilityStability(StrEnum):
    EXPERIMENTAL = "experimental"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    UNAVAILABLE = "unavailable"


class CapabilityRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    name: CapabilityName
    available: bool
    stability: CapabilityStability
    dependency: str | None
    resource_cost: str
    authority_ceiling: str
    schema_version: str = SCHEMA_VERSION
    notes: str = ""


class CapabilityProbe(Protocol):
    """Later waves implement this against VisionMCP / Job Scraper / MTP."""

    def probe(self, name: CapabilityName) -> CapabilityRecord: ...


class CapabilityRegistry:
    """In-process registry. Wave 1 ships static honesty, not live probes."""

    def __init__(self) -> None:
        self._records: dict[CapabilityName, CapabilityRecord] = {}
        self._install_wave1_defaults()

    def _install_wave1_defaults(self) -> None:
        unavailable = (
            CapabilityName.IMAGE_DECODE,
            CapabilityName.OBJECT_SEGMENTATION,
            CapabilityName.DENSE_FEATURES,
            CapabilityName.OCR,
            CapabilityName.LOGO_DETECTION,
            CapabilityName.LOCAL_CORRESPONDENCE,
            CapabilityName.MATERIAL_ANALYSIS,
            CapabilityName.BROWSER_CAPTURE,
            CapabilityName.WORLD_STATE,
            CapabilityName.NEXT_VIEW,
        )
        for name in unavailable:
            self._records[name] = CapabilityRecord(
                name=name,
                available=False,
                stability=CapabilityStability.UNAVAILABLE,
                dependency=None,
                resource_cost="none",
                authority_ceiling="none",
                notes="Wave 1 constitution only; probe lands in a later wave.",
            )
        self._records[CapabilityName.RECEIPT_VERIFY] = CapabilityRecord(
            name=CapabilityName.RECEIPT_VERIFY,
            available=True,
            stability=CapabilityStability.STABLE,
            dependency="searcher.receipts",
            resource_cost="cpu-cheap",
            authority_ceiling="local-recompute",
            notes="Hash-chained receipts verify by recomputation.",
        )

    def register(self, record: CapabilityRecord) -> None:
        self._records[record.name] = record

    def get(self, name: CapabilityName) -> CapabilityRecord:
        return self._records[name]

    def all(self) -> list[CapabilityRecord]:
        return [self._records[name] for name in CapabilityName]

    def probe(self, name: CapabilityName, probe: CapabilityProbe | None = None) -> CapabilityRecord:
        if probe is None:
            return self.get(name)
        record = probe.probe(name)
        self.register(record)
        return record


class CapabilityReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    capabilities: list[CapabilityRecord] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
