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
from searcher.sources.platform import credential_gate_note
from searcher.sources.strategies import missing_key_note

ETSY_KEY_NAMES = ("ETSY_API_KEY",)
ETSY_SIGNUP_URL = "https://developers.etsy.com/documentation/essentials/authentication/"


def etsy_auth_note(*, api_key: str) -> str:
    return missing_key_note(
        key_names=ETSY_KEY_NAMES,
        present={"ETSY_API_KEY": api_key},
        signup_url=ETSY_SIGNUP_URL,
        product="Etsy Open API v3",
    )


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
            known_limitations=[
                "dormant without ETSY_API_KEY",
                f"register an app at {ETSY_SIGNUP_URL}",
                "listing cache <= 6 hours",
                "not part of uncredentialed reach",
            ],
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
            etsy_auth_note(api_key=self.api_key) + ". " + credential_gate_note("Etsy Open API v3"),
        )

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del mode
        return FetchedDocument(
            result=FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=SourceOutcome.AUTH_REQUIRED,
                classification_note=etsy_auth_note(api_key=self.api_key),
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
            note=etsy_auth_note(api_key=self.api_key),
        )
