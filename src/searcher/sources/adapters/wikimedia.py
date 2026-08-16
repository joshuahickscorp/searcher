"""Wikimedia Action API. Zero credential. Identity/alias backbone."""

from __future__ import annotations

from searcher.contracts.enums import Availability, FetchMode, SourceAdmission, SourceOutcome
from searcher.contracts.models import (
    ListingCandidate,
    LiveStatus,
    QueryVariant,
    RatePolicy,
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

LANG_HOSTS = {
    "en": "en.wikipedia.org",
    "ja": "ja.wikipedia.org",
    "fr": "fr.wikipedia.org",
    "it": "it.wikipedia.org",
    "ko": "ko.wikipedia.org",
    "zh": "zh.wikipedia.org",
    "ru": "ru.wikipedia.org",
}


class WikimediaAdapter:
    def __init__(self, *, escalator: Escalator | None = None) -> None:
        self.escalator = escalator
        self._manifest = build_manifest(
            source_id="wikimedia",
            adapter="wikimedia",
            domain="en.wikipedia.org",
            access_method="action_api",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="Action API + article HTML except Special/talk",
            source_class="reference",
            capabilities=["text_search"],
            languages=list(LANG_HOSTS),
            robots_policy="Allow /wiki/ except Special: and talk/admin",
            disallowed_path_prefixes=["/wiki/Special:", "/wiki/Talk:"],
            rate_policy=RatePolicy(requests_per_minute=20, burst=1, concurrent=1),
        )

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        return SourceHealth(
            source_id="wikimedia",
            last_outcome=SourceOutcome.NOT_ATTEMPTED,
            last_checked_at=utc_now(),
        )

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del cursor
        # /w/api.php is Disallow:/w/ for User-agent:*. Use article HTML, which is allowed.
        host = LANG_HOSTS.get(query.language, "en.wikipedia.org")
        slug = query.query_text.replace(" ", "_")
        url = f"https://{host}/wiki/{slug}"
        return DiscoveryPageResult([url], [], None, SourceOutcome.NOT_ATTEMPTED.value)

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del mode
        if self.escalator is None:
            raise RuntimeError("WikimediaAdapter requires an Escalator")
        return self.escalator.fetch(url, self._manifest, source_id="wikimedia")

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        if fetch.result.outcome is not SourceOutcome.SEARCHED_MATCHES_FOUND:
            return []
        html = fetch.body.decode("utf-8", errors="replace")
        payload = extract_listing(html, fetch.final_url or fetch.result.url)
        payload["images"] = [{"url": img} for img in payload.get("images") or []]
        return [
            RawListing(
                source_adapter="wikimedia",
                url=fetch.final_url or fetch.result.url,
                payload=payload,
                content_digest=fetch.result.content_digest or sha256_hex(fetch.body),
                fetched_at=utc_now(),
            )
        ]

    def normalize(self, raw: RawListing) -> ListingCandidate:
        return normalize_raw(raw)

    def live_check(self, candidate: ListingCandidate) -> LiveStatus:
        del candidate
        return LiveStatus(availability=Availability.UNKNOWN, checked_at=utc_now())
