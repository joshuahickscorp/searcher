"""Internet Archive. Historical evidence only — never live."""

from __future__ import annotations

from urllib.parse import quote

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
from searcher.sources.adapters.generic_page import extract_listing
from searcher.sources.adapters.protocol import DiscoveryPageResult
from searcher.sources.fetch_modes import Escalator, FetchedDocument
from searcher.sources.manifest import build_manifest


class ArchiveOrgAdapter:
    def __init__(self, *, escalator: Escalator | None = None) -> None:
        self.escalator = escalator
        self._manifest = build_manifest(
            source_id="archive_org",
            adapter="archive_org",
            domain="archive.org",
            access_method="http_get",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="historical captures; never treat as live",
            source_class="sold_archive",
            capabilities=["text_search", "listing_fetch"],
            robots_policy="Disallow /control/ and /report/ only",
            disallowed_path_prefixes=["/control/", "/report/"],
            known_limitations=["captures are historical, never live listings"],
        )

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        return SourceHealth(
            source_id="archive_org",
            last_outcome=SourceOutcome.NOT_ATTEMPTED,
            last_checked_at=utc_now(),
        )

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del cursor
        url = f"https://archive.org/search?query={quote(query.query_text)}"
        return DiscoveryPageResult([url], [], None, SourceOutcome.NOT_ATTEMPTED.value)

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del mode
        if self.escalator is None:
            raise RuntimeError("ArchiveOrgAdapter requires an Escalator")
        return self.escalator.fetch(url, self._manifest, source_id="archive_org")

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        if fetch.result.outcome is not SourceOutcome.SEARCHED_MATCHES_FOUND:
            return []
        html = fetch.body.decode("utf-8", errors="replace")
        payload = extract_listing(html, fetch.final_url or fetch.result.url)
        payload["availability"] = Availability.UNKNOWN.value
        payload["images"] = [{"url": img} for img in payload.get("images") or []]
        return [
            RawListing(
                source_adapter="archive_org",
                url=fetch.final_url or fetch.result.url,
                payload=payload,
                content_digest=fetch.result.content_digest or sha256_hex(fetch.body),
                fetched_at=utc_now(),
            )
        ]

    def normalize(self, raw: RawListing) -> ListingCandidate:
        candidate = normalize_raw(raw)
        return candidate.model_copy(update={"availability": Availability.UNKNOWN})

    def live_check(self, candidate: ListingCandidate) -> LiveStatus:
        del candidate
        return LiveStatus(
            availability=Availability.UNKNOWN,
            checked_at=utc_now(),
            note="archive capture is never live",
        )
