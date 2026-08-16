"""Etsy Open API v3 only. Dormant AUTH_REQUIRED without a key. Never scrape /search."""

from __future__ import annotations

import os

from searcher.contracts.enums import Availability, FetchMode, SourceAdmission, SourceOutcome
from searcher.contracts.models import (
    FetchResult,
    ListingCandidate,
    LiveStatus,
    QueryVariant,
    RawListing,
    SourceHealth,
    SourceManifest,
)
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.normalization.listing import normalize_raw
from searcher.sources.adapters.protocol import DiscoveryPageResult
from searcher.sources.fetch_modes import FetchedDocument
from searcher.sources.manifest import build_manifest


class EtsyApiAdapter:
    def __init__(self) -> None:
        self.api_key = os.environ.get("ETSY_API_KEY") or ""
        self._manifest = build_manifest(
            source_id="etsy",
            adapter="etsy_api",
            domain="api.etsy.com",
            access_method="official_api",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="Open API v3 only; screen-scraping is not allowed",
            source_class="resale",
            capabilities=["text_search", "listing_fetch", "sold_status", "live_check"],
            authentication="api_key",
            robots_policy="Disallow: /search?*q= ; Applications must not sidestep the API",
            disallowed_path_prefixes=["/search?", "/search?"],
            known_limitations=["dormant without ETSY_API_KEY", "listing cache <= 6 hours"],
        )

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        outcome = SourceOutcome.AUTH_REQUIRED if not self.api_key else SourceOutcome.NOT_ATTEMPTED
        return SourceHealth(source_id="etsy", last_outcome=outcome, last_checked_at=utc_now())

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del query, cursor
        return DiscoveryPageResult(
            [],
            [],
            None,
            SourceOutcome.AUTH_REQUIRED.value,
            "ETSY_API_KEY not configured" if not self.api_key else "oauth not implemented",
        )

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del mode
        return FetchedDocument(
            result=FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=SourceOutcome.AUTH_REQUIRED,
                classification_note="Etsy adapter is API-only and has no credential",
            ),
            body=b"",
            headers={},
            final_url=url,
        )

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        del fetch
        return []

    def normalize(self, raw: RawListing) -> ListingCandidate:
        return normalize_raw(raw)

    def live_check(self, candidate: ListingCandidate) -> LiveStatus:
        del candidate
        return LiveStatus(
            availability=Availability.UNKNOWN,
            checked_at=utc_now(),
            outcome=SourceOutcome.AUTH_REQUIRED,
            note="API credential required",
        )
