"""Sitemap-first discovery for sources whose search paths are disallowed."""

from __future__ import annotations

import re
from xml.etree import ElementTree

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

_LOC = re.compile(r"<loc>\s*([^<]+)\s*</loc>", re.I)


def parse_sitemap_locs(body: bytes, *, limit: int = 200) -> list[str]:
    text = body.decode("utf-8", errors="replace")
    found = [match.group(1).strip() for match in _LOC.finditer(text)]
    if found:
        return found[:limit]
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []
    locs: list[str] = []
    for node in root.iter():
        if node.tag.lower().endswith("loc") and node.text:
            locs.append(node.text.strip())
            if len(locs) >= limit:
                break
    return locs


def filter_locs(locs: list[str], query: str, prefixes: list[str]) -> list[str]:
    tokens = [part.lower() for part in query.split() if len(part) > 2]
    out: list[str] = []
    for loc in locs:
        if prefixes and not any(prefix in loc for prefix in prefixes):
            continue
        lowered = loc.lower()
        if tokens and not any(
            token.replace(" ", "-") in lowered or token in lowered for token in tokens
        ):  # noqa: E501
            continue
        out.append(loc)
    return out


class SitemapAdapter:
    def __init__(
        self,
        *,
        sitemap_url: str,
        prefixes: list[str] | None = None,
        escalator: Escalator | None = None,
        source_id: str = "sitemap",
    ) -> None:
        self.sitemap_url = sitemap_url
        self.prefixes = prefixes or []
        self.escalator = escalator
        self._manifest = build_manifest(
            source_id=source_id,
            adapter="sitemap",
            domain=sitemap_url.split("/")[2] if "://" in sitemap_url else "sitemap",
            access_method="http_get",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="sitemap loc extraction",
            source_class="general_web",
            capabilities=["listing_fetch", "pagination"],
            sitemap_urls=[sitemap_url],
        )

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        return SourceHealth(
            source_id=self._manifest.source_id,
            last_outcome=SourceOutcome.NOT_ATTEMPTED,
            last_checked_at=utc_now(),
        )

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del query, cursor
        return DiscoveryPageResult(
            [self.sitemap_url],
            [],
            None,
            SourceOutcome.NOT_ATTEMPTED.value,
            "sitemap seed",
        )

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del mode
        if self.escalator is None:
            raise RuntimeError("SitemapAdapter requires an Escalator")
        return self.escalator.fetch(url, self._manifest, source_id=self._manifest.source_id)

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        if fetch.result.outcome is not SourceOutcome.SEARCHED_MATCHES_FOUND:
            return []
        locs = parse_sitemap_locs(fetch.body)
        listings: list[RawListing] = []
        for loc in locs:
            listings.append(
                RawListing(
                    source_adapter="sitemap",
                    url=loc,
                    payload={"canonical_url": loc, "extraction_method": "sitemap", "title": loc},
                    content_digest=sha256_hex(loc.encode()),
                    fetched_at=utc_now(),
                )
            )
        return listings

    def normalize(self, raw: RawListing) -> ListingCandidate:
        return normalize_raw(raw)

    def live_check(self, candidate: ListingCandidate) -> LiveStatus:
        del candidate
        return LiveStatus(availability=Availability.UNKNOWN, checked_at=utc_now())
