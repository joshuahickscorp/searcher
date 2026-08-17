"""Self-hosted SearxNG. SOURCE_UNAVAILABLE when SEARCHER_SEARX_URL is unset."""

from __future__ import annotations

import json
import os
from urllib.parse import urlencode

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
from searcher.core.ids import new_id, sha256_hex
from searcher.core.time import utc_now
from searcher.normalization.listing import normalize_raw
from searcher.sources.adapters.protocol import DiscoveryPageResult
from searcher.sources.fetch_modes import Escalator, FetchedDocument
from searcher.sources.manifest import build_manifest


class SearxAdapter:
    def __init__(self, *, endpoint: str | None = None, escalator: Escalator | None = None) -> None:
        self.endpoint = (endpoint or os.environ.get("SEARCHER_SEARX_URL") or "").rstrip("/")
        self.escalator = escalator
        self._manifest = build_manifest(
            source_id="searx",
            adapter="searx",
            domain="localhost",
            access_method="self_hosted_api",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="own SearxNG JSON search only",
            source_class="metasearch",
            capabilities=["text_search"],
            languages=["en", "ja", "ko", "zh", "fr", "it", "ru"],
            robots_policy="n/a (self-hosted)",
            known_limitations=[
                "public instances must not be the production path",
                "optional web-wide path; unset SEARCHER_SEARX_URL leaves shop reach intact",
            ],
        )

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        outcome = (
            SourceOutcome.SOURCE_UNAVAILABLE if not self.endpoint else SourceOutcome.NOT_ATTEMPTED
        )
        return SourceHealth(
            source_id="searx",
            last_outcome=outcome,
            last_checked_at=utc_now(),
        )

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        if not self.endpoint:
            return DiscoveryPageResult(
                [],
                [],
                None,
                SourceOutcome.SOURCE_UNAVAILABLE.value,
                "SEARCHER_SEARX_URL is not configured",
            )
        params = {"q": query.query_text, "format": "json"}
        if cursor:
            params["pageno"] = cursor
        url = f"{self.endpoint}/search?{urlencode(params)}"
        return DiscoveryPageResult(
            [url], [], None, SourceOutcome.NOT_ATTEMPTED.value, "searx query"
        )  # noqa: E501

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del mode
        if self.escalator is None:
            raise RuntimeError("SearxAdapter requires an Escalator")
        if not self.endpoint:
            return FetchedDocument(
                result=FetchResult(
                    attempt_id=new_id(),
                    url=url,
                    outcome=SourceOutcome.SOURCE_UNAVAILABLE,
                    classification_note="SEARCHER_SEARX_URL is not configured",
                ),
                body=b"",
                headers={},
                final_url=url,
            )
        return self.escalator.fetch(url, self._manifest, source_id="searx")

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        if fetch.result.outcome is SourceOutcome.SOURCE_UNAVAILABLE:
            return []
        if fetch.result.outcome is not SourceOutcome.SEARCHED_MATCHES_FOUND:
            return []
        try:
            payload = json.loads(fetch.body.decode("utf-8"))
        except json.JSONDecodeError:
            return []
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            return []
        listings: list[RawListing] = []
        for item in results:
            if not isinstance(item, dict) or not item.get("url"):
                continue
            listings.append(
                RawListing(
                    source_adapter="searx",
                    url=str(item["url"]),
                    payload={
                        "title": item.get("title"),
                        "description": item.get("content") or item.get("snippet"),
                        "canonical_url": item.get("url"),
                        "extraction_method": "api",
                        "images": [{"url": item["thumbnail"]}] if item.get("thumbnail") else [],
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
