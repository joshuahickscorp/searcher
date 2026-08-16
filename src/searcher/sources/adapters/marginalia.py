"""Marginalia Search API. public key works with no signup. CC-BY-NC-SA 4.0."""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode

from searcher.contracts.enums import Availability, FetchMode, SourceAdmission, SourceOutcome
from searcher.contracts.models import (
    ListingCandidate,
    LiveStatus,
    QueryVariant,
    RawListing,
    SourceHealth,
    SourceManifest,
)
from searcher.core.ids import sha256_hex
from searcher.core.time import utc_now
from searcher.normalization.listing import normalize_raw
from searcher.sources.adapters.protocol import DiscoveryPageResult
from searcher.sources.fetch_modes import Escalator, FetchedDocument
from searcher.sources.manifest import build_manifest


class MarginaliaAdapter:
    def __init__(self, *, escalator: Escalator | None = None, api_key: str | None = None) -> None:
        self.escalator = escalator
        self.api_key = api_key or os.environ.get("MARGINALIA_API_KEY") or "public"
        self._manifest = build_manifest(
            source_id="marginalia",
            adapter="marginalia",
            domain="api2.marginalia-search.com",
            access_method="official_api",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="non-commercial default CC-BY-NC-SA 4.0",
            source_class="general_web",
            capabilities=["text_search"],
            authentication="api_key",
            known_limitations=["shared public key often 503s", "weak for live listings"],
        )

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        return SourceHealth(
            source_id="marginalia",
            last_outcome=SourceOutcome.NOT_ATTEMPTED,
            last_checked_at=utc_now(),
        )

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del cursor
        url = "https://api2.marginalia-search.com/search?" + urlencode({"query": query.query_text})
        return DiscoveryPageResult([url], [], None, SourceOutcome.NOT_ATTEMPTED.value)

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del mode
        if self.escalator is None:
            raise RuntimeError("MarginaliaAdapter requires an Escalator")
        return self.escalator.fetch(
            url,
            self._manifest,
            source_id="marginalia",
            extra_headers={"API-Key": self.api_key},
        )

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        if fetch.result.outcome is not SourceOutcome.SEARCHED_MATCHES_FOUND:
            return []
        try:
            payload = json.loads(fetch.body.decode("utf-8"))
        except json.JSONDecodeError:
            return []
        results = payload.get("results") if isinstance(payload, dict) else None
        if results is None and isinstance(payload, list):
            results = payload
        if not isinstance(results, list):
            return []
        listings: list[RawListing] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("link")
            if not url:
                continue
            listings.append(
                RawListing(
                    source_adapter="marginalia",
                    url=str(url),
                    payload={
                        "title": item.get("title"),
                        "description": item.get("description"),
                        "canonical_url": url,
                        "extraction_method": "api",
                    },
                    content_digest=sha256_hex(json.dumps(item, sort_keys=True).encode()),
                    fetched_at=utc_now(),
                )
            )
        return listings

    def normalize(self, raw: RawListing) -> ListingCandidate:
        return normalize_raw(raw)

    def live_check(self, candidate: ListingCandidate) -> LiveStatus:
        del candidate
        return LiveStatus(availability=Availability.UNKNOWN, checked_at=utc_now())
