"""§28.1 cost hierarchy. Heavyweight stages cannot run before deduplication."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from searcher.core.errors import InvariantViolation
from searcher.core.time import utc_now


class CostStage(StrEnum):
    CACHE = "cache"
    HASHES_METADATA = "hashes_and_metadata"
    TEXT_OCR = "text_and_ocr"
    GLOBAL_EMBEDDINGS = "global_embeddings"
    DEDUPLICATION = "deduplication"
    LOCAL_PARTS = "local_part_extraction"
    LOCAL_CORRESPONDENCE = "local_correspondence"
    BROWSER = "browser_rendering"
    DELIBERATIVE = "deliberative_vlm"
    REMOTE_MODEL = "remote_model"
    DEEP_AUTHENTICITY = "deep_authenticity"


CHEAP_STAGES: frozenset[CostStage] = frozenset(
    {
        CostStage.CACHE,
        CostStage.HASHES_METADATA,
        CostStage.TEXT_OCR,
        CostStage.GLOBAL_EMBEDDINGS,
        CostStage.DEDUPLICATION,
    }
)

HEAVYWEIGHT_STAGES: frozenset[CostStage] = frozenset(
    {
        CostStage.LOCAL_PARTS,
        CostStage.LOCAL_CORRESPONDENCE,
        CostStage.BROWSER,
        CostStage.DELIBERATIVE,
        CostStage.REMOTE_MODEL,
        CostStage.DEEP_AUTHENTICITY,
    }
)

STAGE_ORDER: tuple[CostStage, ...] = (
    CostStage.CACHE,
    CostStage.HASHES_METADATA,
    CostStage.TEXT_OCR,
    CostStage.GLOBAL_EMBEDDINGS,
    CostStage.DEDUPLICATION,
    CostStage.LOCAL_PARTS,
    CostStage.LOCAL_CORRESPONDENCE,
    CostStage.BROWSER,
    CostStage.DELIBERATIVE,
    CostStage.REMOTE_MODEL,
    CostStage.DEEP_AUTHENTICITY,
)


class CostEvent:
    __slots__ = ("stage", "at", "detail", "model_call", "bytes_touched")

    def __init__(
        self,
        stage: CostStage,
        *,
        detail: str = "",
        model_call: bool = False,
        bytes_touched: int = 0,
    ) -> None:
        self.stage = stage
        self.at = utc_now()
        self.detail = detail
        self.model_call = model_call
        self.bytes_touched = bytes_touched


class CostLedger:
    """Ordered record of work. The guard is executable, not a comment."""

    def __init__(self, *, search_id: str | None = None) -> None:
        self.search_id = search_id
        self.events: list[CostEvent] = []
        self._deduped = False
        self.cache_hits = 0
        self.model_calls = 0
        self.bytes_touched = 0
        self.dedup_savings = 0

    @property
    def deduplicated(self) -> bool:
        return self._deduped

    def mark_deduplicated(self, *, families_collapsed: int = 0) -> None:
        self._deduped = True
        self.dedup_savings += max(0, families_collapsed)
        self.record(CostStage.DEDUPLICATION, detail=f"collapsed={families_collapsed}")

    def record(
        self,
        stage: CostStage,
        *,
        detail: str = "",
        model_call: bool = False,
        bytes_touched: int = 0,
    ) -> CostEvent:
        if stage in HEAVYWEIGHT_STAGES and not self._deduped:
            raise InvariantViolation(
                f"heavyweight stage {stage} cannot run before deduplication (§28.2)",
                search_id=self.search_id,
            )
        if model_call and stage in HEAVYWEIGHT_STAGES and not self._deduped:
            raise InvariantViolation(
                "heavyweight model call cannot run before deduplication",
                search_id=self.search_id,
            )
        event = CostEvent(stage, detail=detail, model_call=model_call, bytes_touched=bytes_touched)
        self.events.append(event)
        self.bytes_touched += max(0, bytes_touched)
        if model_call:
            self.model_calls += 1
        if stage is CostStage.CACHE and "hit" in detail:
            self.cache_hits += 1
        return event

    def stage_names(self) -> list[str]:
        return [event.stage.value for event in self.events]

    def first_index(self, stage: CostStage) -> int | None:
        for index, event in enumerate(self.events):
            if event.stage is stage:
                return index
        return None

    def cheap_first_respected(self) -> bool:
        """True when no heavyweight event precedes the first dedup event."""
        dedup_at = self.first_index(CostStage.DEDUPLICATION)
        for index, event in enumerate(self.events):
            if event.stage in HEAVYWEIGHT_STAGES and (dedup_at is None or index < dedup_at):
                return False
        return True

    def as_payload(self) -> dict[str, Any]:
        return {
            "search_id": self.search_id,
            "stages": self.stage_names(),
            "cache_hits": self.cache_hits,
            "model_calls": self.model_calls,
            "bytes_touched": self.bytes_touched,
            "dedup_savings": self.dedup_savings,
            "deduplicated": self._deduped,
            "cheap_first": self.cheap_first_respected(),
        }
