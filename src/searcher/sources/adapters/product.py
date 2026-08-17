"""Shared product-page adapter driven by a recorded SourceSpec."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse

from searcher.contracts.enums import (
    DocumentClass,
    FetchMode,
    SourceAdmission,
    SourceOutcome,
)
from searcher.contracts.models import (
    QueryVariant,
    RatePolicy,
    RawListing,
    SourceManifest,
)
from searcher.core.ids import sha256_hex
from searcher.sources.adapters.generic_page import GenericPageAdapter, listing_links
from searcher.sources.adapters.protocol import DiscoveryPageResult
from searcher.sources.classify import classify_acquired_document
from searcher.sources.expand import raw_listing_from_member, shopify_members_from_body
from searcher.sources.fetch_modes import FetchedDocument
from searcher.sources.manifest import build_manifest
from searcher.sources.robots import path_matches_prefix


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source_id: str
    adapter: str
    domain: str
    access_method: str
    admission: SourceAdmission
    allowed_use: str
    source_class: str
    robots_policy: str
    languages: tuple[str, ...]
    disallowed: tuple[str, ...]
    listing_prefixes: tuple[str, ...]
    sitemap_urls: tuple[str, ...] = ()
    enabled: bool = True
    open_question: str | None = None
    capabilities: tuple[str, ...] = ("listing_fetch", "live_check")
    rpm: int = 12
    known_limitations: tuple[str, ...] = ()
    collection_paths: tuple[str, ...] = ()
    query_paths: tuple[str, ...] = ()
    catalog_feed_path: str | None = None
    catalog_page_param: str = "page"
    catalog_page_size: int = 250
    origin: str | None = None


def manifest_from_spec(spec: SourceSpec) -> SourceManifest:
    return build_manifest(
        source_id=spec.source_id,
        adapter=spec.adapter,
        domain=spec.domain,
        access_method=spec.access_method,
        admission_status=spec.admission,
        allowed_use=spec.allowed_use,
        source_class=spec.source_class,
        capabilities=list(spec.capabilities),
        robots_policy=spec.robots_policy,
        languages=list(spec.languages),
        enabled=spec.enabled,
        disallowed_path_prefixes=list(spec.disallowed),
        open_question=spec.open_question,
        sitemap_urls=list(spec.sitemap_urls),
        listing_path_prefixes=list(spec.listing_prefixes),
        rate_policy=RatePolicy(requests_per_minute=spec.rpm, burst=2, concurrent=1),
        known_limitations=list(spec.known_limitations),
        fetch_modes=[FetchMode.CACHE, FetchMode.HTTP],
    )


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def usable_query_text(raw: str | None) -> str:
    text = " ".join(str(raw or "").replace('"', " ").replace("'", " ").split())
    letters = re.sub(r"[^\w]+", "", text, flags=re.UNICODE)
    if len(letters) < 2:
        return ""
    return text


def slugify_query(text: str) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug


def query_slugs(text: str) -> list[str]:
    """Vendor-like collection handles only.

    Shopify collection URLs are brand slugs. Emitting the full query as a
    handle produces empty 200 JSON pages that consume the source budget
    before the real vendor collection is fetched.
    """
    parts = [part for part in text.split() if part]
    if len(parts) >= 2:
        brand = slugify_query(" ".join(parts[:2]))
        if brand:
            return [brand]
    if parts:
        one = slugify_query(parts[0])
        if one:
            return [one]
    return []


def parse_shopify_catalog(body: bytes, url: str, spec: SourceSpec) -> list[RawListing]:
    parsed = urlparse(url)
    origin = (
        f"{parsed.scheme}://{parsed.netloc}"
        if parsed.scheme and parsed.netloc
        else f"https://{spec.domain}"
    )
    language = spec.languages[0] if spec.languages else None
    listings: list[RawListing] = []
    for member in shopify_members_from_body(body, url, origin=origin):
        listings.append(
            raw_listing_from_member(
                member,
                source_adapter=spec.adapter,
                content_digest=sha256_hex(member.url.encode("utf-8")),
                language=language,
            )
        )
    return listings


class ProductPageAdapter(GenericPageAdapter):
    spec: SourceSpec

    def __init__(self, spec: SourceSpec) -> None:
        self.spec = spec
        super().__init__(manifest_from_spec(spec))

    def _blocked_url(self, url: str) -> bool:
        return path_matches_prefix(url, list(self.spec.disallowed))

    def _query_seeds(self, terms: str) -> list[str]:
        quoted = quote_plus(terms)
        seeds: list[str] = []
        templates = list(self.spec.query_paths)
        shopify_like = any(path.startswith("/collections") for path in self.spec.collection_paths)
        if shopify_like and not templates:
            templates = ["/collections/{slug}/products.json?limit=250"]
        slugs = query_slugs(terms) or [slugify_query(terms)]
        for template in templates:
            if "{slug}" in template:
                for slug in slugs:
                    if not slug:
                        continue
                    seeds.append(
                        f"https://{self.spec.domain}{template.format(slug=slug, query=quoted)}"
                    )
            else:
                slug = slugs[0] if slugs else quoted
                path = template.format(query=quoted, slug=slug)
                seeds.append(f"https://{self.spec.domain}{path}")
        for path in self.spec.collection_paths:
            if "{query}" in path:
                seeds.append(f"https://{self.spec.domain}{path.format(query=quoted)}")
        out: list[str] = []
        seen: set[str] = set()
        for url in seeds:
            if url in seen or self._blocked_url(url):
                continue
            seen.add(url)
            out.append(url)
        return out

    def _fallback_seeds(self) -> list[str]:
        seeds: list[str] = []
        for path in self.spec.collection_paths:
            if "{query}" in path:
                continue
            seeds.append(f"https://{self.spec.domain}{path}")
        seeds.extend(self.spec.sitemap_urls)
        out: list[str] = []
        seen: set[str] = set()
        for url in seeds:
            if url in seen or self._blocked_url(url):
                continue
            seen.add(url)
            out.append(url)
        return out

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del cursor
        if not self.spec.enabled:
            return DiscoveryPageResult(
                [],
                [],
                None,
                SourceOutcome.BLOCKED_BY_POLICY.value,
                self.spec.open_question or "disabled",
            )
        from searcher.sources.strategies import discover_seed_urls, plan_strategies

        terms = usable_query_text(query.query_text)
        if terms:
            planned = plan_strategies(self.spec, terms)
            seeds = discover_seed_urls(planned)
            note = "query"
        else:
            seeds = self._fallback_seeds()
            note = "fallback"
        if not seeds:
            return DiscoveryPageResult(
                [], [], None, SourceOutcome.NOT_ATTEMPTED.value, note or "no seed paths"
            )
        return DiscoveryPageResult(seeds, [], None, SourceOutcome.NOT_ATTEMPTED.value, note)

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        url = fetch.final_url or fetch.result.url
        document = classify_acquired_document(
            url=url,
            body=fetch.body,
            content_type=fetch.result.content_type,
            listing_prefixes=list(self.spec.listing_prefixes),
        )
        if document is DocumentClass.INDEX:
            return []
        if document is DocumentClass.PRODUCT:
            listings = parse_shopify_catalog(fetch.body, url, self.spec)
            if listings:
                return listings
        listings = super().parse(fetch)
        language = self.spec.languages[0] if self.spec.languages else None
        if language:
            for listing in listings:
                listing.payload["language"] = language
                listing.payload["source_region"] = language
        return listings

    def listing_urls_from(self, html: str, url: str) -> list[str]:
        path = urlparse(url).path
        if (
            path.endswith(".json")
            or html.lstrip().startswith('{"products"')
            or html.lstrip().startswith('{"product"')
        ):
            listings = parse_shopify_catalog(html.encode("utf-8"), url, self.spec)
            return [item.url for item in listings]
        return listing_links(html, url, list(self.spec.listing_prefixes))


# Recorded from docs/sources/SOURCE_RESEARCH_2026-08-16.md

REALREAL = SourceSpec(
    source_id="the_realreal",
    adapter="the_realreal",
    domain="www.therealreal.com",
    access_method="http_get",
    admission=SourceAdmission.ADMITTED,
    allowed_use="item pages and sitemap; no before/after pagination",
    source_class="consignment",
    robots_policy="Disallow cart/checkout/login and ?*before= ?*after= on shop/designers/products",
    languages=("en",),
    disallowed=("/cart", "/checkout", "/login", "/admin", "/consign", "before=", "after="),
    listing_prefixes=("/products/",),
    sitemap_urls=("https://www.therealreal.com/sitemaps/sitemap_index.xml",),
    capabilities=("listing_fetch", "live_check", "pagination"),
)

REBAG = SourceSpec(
    source_id="rebag",
    adapter="rebag",
    domain="www.rebag.com",
    access_method="http_get",
    admission=SourceAdmission.ADMITTED,
    allowed_use="product pages",
    source_class="consignment",
    robots_policy="Disallow /digital_certificate/",
    languages=("en",),
    disallowed=("/digital_certificate/",),
    listing_prefixes=("/shop/", "/products/"),
    sitemap_urls=("https://www.rebag.com/sitemap.xml",),
)

KOMEHYO = SourceSpec(
    source_id="komehyo",
    adapter="komehyo",
    domain="komehyo.jp",
    access_method="http_get",
    admission=SourceAdmission.ADMITTED,
    allowed_use="product pages and sitemap",
    source_class="consignment",
    robots_policy="User-agent: * and sitemaps only. No Disallow.",
    languages=("ja", "en"),
    disallowed=(),
    listing_prefixes=("/c/goods/", "/shop/", "/product"),
    sitemap_urls=("https://komehyo.jp/sitemap.xml",),
)

KIND = SourceSpec(
    source_id="kind",
    adapter="kind",
    domain="shop.kind.co.jp",
    access_method="http_get",
    admission=SourceAdmission.ADMITTED,
    allowed_use="product and collection pages; not /search",
    source_class="vintage_archive",
    robots_policy="Disallow: /search",
    languages=("ja", "en"),
    disallowed=("/search",),
    listing_prefixes=("/products/",),
    sitemap_urls=("https://shop.kind.co.jp/sitemap.xml",),
    collection_paths=("/collections/all",),
    query_paths=("/collections/{slug}/products.json?limit=250",),
    catalog_feed_path="/products.json",
    catalog_page_param="page",
    catalog_page_size=250,
)

BYRONESQUE = SourceSpec(
    source_id="byronesque",
    adapter="byronesque",
    domain="byronesque.com",
    access_method="http_get",
    admission=SourceAdmission.ADMITTED,
    allowed_use="WordPress public pages",
    source_class="vintage_archive",
    robots_policy="Disallow /wp-admin/",
    languages=("en",),
    disallowed=("/wp-admin/",),
    listing_prefixes=("/product", "/shop/"),
    sitemap_urls=("https://byronesque.com/sitemap_index.xml",),
    query_paths=("/?s={query}",),
)

HEROINE = SourceSpec(
    source_id="heroine",
    adapter="heroine",
    domain="shopheroine.com",
    access_method="http_get",
    admission=SourceAdmission.ADMITTED,
    allowed_use="public pages",
    source_class="vintage_archive",
    robots_policy="User-agent: * Disallow: (empty)",
    languages=("en",),
    disallowed=(),
    listing_prefixes=("/products/", "/product/"),
    collection_paths=("/collections/all",),
    query_paths=("/collections/{slug}/products.json?limit=250", "/search?q={query}"),
    catalog_feed_path="/collections/all/products.json",
    catalog_page_param="page",
    catalog_page_size=250,
    open_question="Is shopheroine.com the intended Heroine storefront?",
)

MERCARI_JP = SourceSpec(
    source_id="mercari_jp",
    adapter="mercari_jp",
    domain="jp.mercari.com",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="public item pages; never /v1/ /v2/",
    source_class="regional",
    robots_policy="Disallow /mypage/ /purchase/ /sell/ /transaction/ /v1/ /v2/",
    languages=("ja",),
    disallowed=("/mypage/", "/purchase/", "/sell/", "/transaction/", "/v1/", "/v2/"),
    listing_prefixes=("/item/",),
    enabled=False,
    open_question="Terms of automated access were not fetched on 2026-08-16.",
)

YAHOO_AUCTIONS = SourceSpec(
    source_id="yahoo_auctions",
    adapter="yahoo_auctions",
    domain="auctions.yahoo.co.jp",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="public item pages; not /closedsearch",
    source_class="auction",
    robots_policy="Disallow members/sell/user/watchlists and /closedsearch",
    languages=("ja",),
    disallowed=("/closedsearch", "/jp/show/mystatus", "/sell"),
    listing_prefixes=("/jp/auction/",),
    enabled=False,
    open_question="Item HTML fetchability without login was not confirmed.",
)

BUYEE = SourceSpec(
    source_id="buyee",
    adapter="buyee",
    domain="buyee.jp",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="public catalog; link only; never bid",
    source_class="regional",
    robots_policy="Disallow account/order/api/internal and /mercari/item/description/",
    languages=("ja", "en"),
    disallowed=("/api/v1/", "/internalapi/", "/mercari/item/description/"),
    listing_prefixes=("/item/", "/yahooauc/item/"),
    enabled=False,
    open_question="Full Terms of Use beyond the caution page were not fetched.",
)

VINTED = SourceSpec(
    source_id="vinted",
    adapter="vinted",
    domain="www.vinted.com",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="public item pages for search/discovery only",
    source_class="resale",
    robots_policy="Content-Signal: ai-train=no, search=yes, ai-input=yes",
    languages=("en", "fr", "de", "it"),
    disallowed=(),
    listing_prefixes=("/items/",),
    enabled=False,
    open_question="Does part-level comparison count as search or ai-input?",
)

BUNJANG = SourceSpec(
    source_id="bunjang",
    adapter="bunjang",
    domain="m.bunjang.co.kr",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="public pages except login/apps/talk",
    source_class="regional",
    robots_policy="Allow / except login/apps/talk",
    languages=("ko",),
    disallowed=("/login", "/apps", "/talk"),
    listing_prefixes=("/products/",),
    enabled=False,
    open_question="Is a listing complete without JS?",
)

SSENSE = SourceSpec(
    source_id="ssense",
    adapter="ssense",
    domain="www.ssense.com",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="product pages; never ?q= or /api/",
    source_class="retailer_archive",
    robots_policy="Disallow /*?q=* /*?page=* /api/",
    languages=("en", "fr"),
    disallowed=("/api/", "?q=", "?page="),
    listing_prefixes=("/men/product/", "/women/product/"),
    enabled=False,
    open_question="JSON-LD and sold markers unverified.",
)

FARFETCH = SourceSpec(
    source_id="farfetch",
    adapter="farfetch",
    domain="www.farfetch.com",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="product pages; never /search",
    source_class="retailer_archive",
    robots_policy="Disallow */search",
    languages=("en",),
    disallowed=("/search",),
    listing_prefixes=("/shopping/", "/item/"),
    enabled=False,
    open_question="JSON-LD unverified.",
)

STOCKX = SourceSpec(
    source_id="stockx",
    adapter="stockx",
    domain="stockx.com",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="product pages; never /search or /api/",
    source_class="resale",
    robots_policy="Disallow */search* /api/ /listings",
    languages=("en",),
    disallowed=("/search", "/api/", "/listings"),
    listing_prefixes=(),
    enabled=False,
    open_question="Heavy bot wall historically; live HTML unverified.",
)

GOAT = SourceSpec(
    source_id="goat",
    adapter="goat",
    domain="www.goat.com",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="product pages; never /search",
    source_class="resale",
    robots_policy="Disallow /search /new-search*",
    languages=("en",),
    disallowed=("/search", "/new-search"),
    listing_prefixes=("/sneakers/", "/apparel/"),
    enabled=False,
    open_question="Do not treat /web-api/ as a public API.",
)

POSHMARK = SourceSpec(
    source_id="poshmark",
    adapter="poshmark",
    domain="poshmark.com",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="individual listing pages; never /search /listings /api",
    source_class="resale",
    robots_policy="Disallow /search /listings /api",
    languages=("en",),
    disallowed=("/search", "/listings", "/api"),
    listing_prefixes=("/listing/",),
    enabled=False,
    open_question="Sold closet badge unverified.",
)

DUCKDUCKGO = SourceSpec(
    source_id="duckduckgo",
    adapter="duckduckgo",
    domain="html.duckduckgo.com",
    access_method="http_get",
    admission=SourceAdmission.REVIEW_REQUIRED,
    allowed_use="HTML search pending ToS review",
    source_class="general_web",
    robots_policy="User-agent: * Allow: /",
    languages=("en",),
    disallowed=(),
    listing_prefixes=(),
    enabled=False,
    open_question="DDG ToS for automated commercial reuse were not fetched.",
    capabilities=("text_search",),
)

SPECS: dict[str, SourceSpec] = {
    spec.source_id: spec
    for spec in (
        REALREAL,
        REBAG,
        KOMEHYO,
        KIND,
        BYRONESQUE,
        HEROINE,
        MERCARI_JP,
        YAHOO_AUCTIONS,
        BUYEE,
        VINTED,
        BUNJANG,
        SSENSE,
        FARFETCH,
        STOCKX,
        GOAT,
        POSHMARK,
        DUCKDUCKGO,
    )
}
