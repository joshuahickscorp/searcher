"""eBay Browse API only. Dormant AUTH_REQUIRED without credentials. Never scrape /sch/."""

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

EBAY_KEY_NAMES = ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET")
EBAY_SIGNUP_URL = "https://developer.ebay.com/api-docs/static/gs_create-the-ebay-api-keysets.html"


def ebay_auth_note(*, client_id: str, client_secret: str) -> str:
    return missing_key_note(
        key_names=EBAY_KEY_NAMES,
        present={"EBAY_CLIENT_ID": client_id, "EBAY_CLIENT_SECRET": client_secret},
        signup_url=EBAY_SIGNUP_URL,
        product="eBay Browse API",
    )


class EbayApiAdapter:
    def __init__(self) -> None:
        self.client_id = os.environ.get("EBAY_CLIENT_ID") or ""
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET") or ""
        self._manifest = build_manifest(
            source_id="ebay",
            adapter="ebay_api",
            domain="api.ebay.com",
            access_method="official_api",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="Browse API only; web /sch/ is not admissible",
            source_class="resale",
            capabilities=["text_search", "listing_fetch", "sold_status", "live_check"],
            authentication="oauth",
            robots_policy="Approved enterprise integrations must use our official API. Disallow: /sch/",  # noqa: E501
            disallowed_path_prefixes=["/sch/", "/sch/i.html"],
            known_limitations=[
                "dormant without EBAY_CLIENT_ID and EBAY_CLIENT_SECRET",
                f"create a keyset at {EBAY_SIGNUP_URL}",
                "not part of uncredentialed reach",
            ],
        )

    def _has_creds(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        outcome = (
            SourceOutcome.AUTH_REQUIRED if not self._has_creds() else SourceOutcome.NOT_ATTEMPTED
        )  # noqa: E501
        return SourceHealth(source_id="ebay", last_outcome=outcome, last_checked_at=utc_now())

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del query, cursor
        note = (
            ebay_auth_note(client_id=self.client_id, client_secret=self.client_secret)
            + ". "
            + credential_gate_note("eBay Browse API")
        )
        return DiscoveryPageResult(
            [],
            [],
            None,
            SourceOutcome.AUTH_REQUIRED.value,
            note,
        )

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del mode
        return FetchedDocument(
            result=FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=SourceOutcome.AUTH_REQUIRED,
                classification_note=ebay_auth_note(
                    client_id=self.client_id, client_secret=self.client_secret
                ),
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
            note=ebay_auth_note(client_id=self.client_id, client_secret=self.client_secret),
        )
