"""§14.3 SourceAdapter protocol."""

from __future__ import annotations

from typing import Protocol

from searcher.contracts.enums import FetchMode
from searcher.contracts.models import (
    ListingCandidate,
    LiveStatus,
    QueryVariant,
    RawListing,
    SourceHealth,
    SourceManifest,
)
from searcher.sources.fetch_modes import FetchedDocument


class DiscoveryPageResult:
    def __init__(
        self,
        urls: list[str],
        raw: list[RawListing],
        cursor: str | None,
        outcome: str,
        note: str = "",
    ) -> None:
        self.urls = urls
        self.raw = raw
        self.cursor = cursor
        self.outcome = outcome
        self.note = note


class SourceAdapter(Protocol):
    def manifest(self) -> SourceManifest: ...

    def health_check(self) -> SourceHealth: ...

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult: ...

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument: ...

    def parse(self, fetch: FetchedDocument) -> list[RawListing]: ...

    def normalize(self, raw: RawListing) -> ListingCandidate: ...

    def live_check(self, candidate: ListingCandidate) -> LiveStatus: ...
