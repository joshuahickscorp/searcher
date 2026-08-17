"""Reach is independent of collection-handle luck and reports every strategy."""

from __future__ import annotations

from searcher.contracts.enums import QueryType, SourceAdmission, SourceOutcome
from searcher.contracts.models import QueryVariant
from searcher.sources.adapters.byronesque import ByronesqueAdapter
from searcher.sources.adapters.ebay_api import EBAY_SIGNUP_URL, EbayApiAdapter, ebay_auth_note
from searcher.sources.adapters.etsy_api import ETSY_SIGNUP_URL, EtsyApiAdapter, etsy_auth_note
from searcher.sources.adapters.kind import KindAdapter
from searcher.sources.adapters.komehyo import KomehyoAdapter
from searcher.sources.adapters.product import KIND, query_slugs
from searcher.sources.adapters.rebag import RebagAdapter
from searcher.sources.adapters.the_realreal import TheRealRealAdapter
from searcher.sources.admission import AdmissionGate
from searcher.sources.catalog import CatalogCaps, catalog_url_allowed, page_catalog
from searcher.sources.http import HonestHttpClient
from searcher.sources.manifest import build_manifest
from searcher.sources.robots import RobotsCache, path_matches_prefix
from searcher.sources.strategies import (
    CATALOG_FEED,
    COLLECTION_SLUG,
    SITE_SEARCH,
    SITEMAP,
    PlannedStrategy,
    format_strategy_detail,
    missing_key_note,
    plan_strategies,
)


def _query(text: str, language: str = "en") -> QueryVariant:
    return QueryVariant(
        query_id="q",
        hypothesis_id="h",
        round=0,
        language=language,
        query_text=text,
        query_type=QueryType.EXACT_NAME,
    )


def _by_name(planned: list[PlannedStrategy], name: str) -> PlannedStrategy:
    for item in planned:
        if item.name == name:
            return item
    raise AssertionError(f"missing strategy {name}")


def test_kind_plans_catalog_feed_not_only_collection_slug() -> None:
    planned = plan_strategies(KIND, "personsoul denim")
    names = [item.name for item in planned]
    assert COLLECTION_SLUG in names
    assert CATALOG_FEED in names
    assert SITE_SEARCH in names
    assert SITEMAP in names
    collection = _by_name(planned, COLLECTION_SLUG)
    catalog = _by_name(planned, CATALOG_FEED)
    search = _by_name(planned, SITE_SEARCH)
    sitemap = _by_name(planned, SITEMAP)
    assert collection.status == "queued"
    assert any("/collections/" in url and "personsoul" in url for url in collection.urls)
    assert catalog.status == "queued"
    assert any("/products.json" in url for url in catalog.urls)
    assert all("/collections/" not in url for url in catalog.urls)
    assert search.status == "skipped"
    assert "search is not an admitted use" in search.reason
    assert sitemap.status == "queued"
    assert any("sitemap.xml" in url for url in sitemap.urls)


def test_kind_japanese_query_still_queues_catalog() -> None:
    planned = plan_strategies(KIND, "ウィリーチャバリア")
    collection = _by_name(planned, COLLECTION_SLUG)
    catalog = _by_name(planned, CATALOG_FEED)
    assert collection.status == "skipped"
    assert "handle" in collection.reason
    assert catalog.status == "queued"


def test_kind_discover_emits_sitemap_and_collection_never_search() -> None:
    page = KindAdapter().discover(_query("personsoul"), None)
    blob = " ".join(page.urls)
    assert "personsoul" in blob
    assert "products.json" in blob
    assert "sitemap.xml" in blob
    assert "/search" not in blob
    assert page.note == "query"


def test_kind_site_search_is_not_queued_even_when_slug_misses() -> None:
    planned = plan_strategies(KIND, "xyzzy-no-such-brand-999")
    search = _by_name(planned, SITE_SEARCH)
    assert search.status == "skipped"
    urls = [url for item in planned for url in item.urls]
    assert all("/search" not in url for url in urls)


def test_shops_without_collection_slugs_use_sitemap() -> None:
    for adapter in (RebagAdapter(), KomehyoAdapter(), TheRealRealAdapter()):
        page = adapter.discover(_query("prada nylon"), None)
        blob = " ".join(page.urls).lower()
        assert page.urls, f"{adapter.spec.source_id} must seed something for a nonempty query"
        assert "sitemap" in blob
        assert "/search" not in blob


def test_byronesque_uses_admitted_site_search() -> None:
    planned = plan_strategies(ByronesqueAdapter().spec, "Margiela jacket")
    search = _by_name(planned, SITE_SEARCH)
    assert search.status == "queued"
    assert any("s=" in url for url in search.urls)
    page = ByronesqueAdapter().discover(_query("Margiela jacket"), None)
    assert any("s=" in url for url in page.urls)


def test_coverage_line_names_each_empty_strategy() -> None:
    planned = plan_strategies(KIND, "personsoul")
    detail = format_strategy_detail([item.as_payload() for item in planned])
    assert "collection_slug" in detail
    assert "catalog_feed" in detail
    assert "site_search" in detail
    assert "sitemap" in detail
    assert "skipped" in detail
    assert "search is not an admitted use" in detail


def test_ebay_auth_names_keys_and_signup_url() -> None:
    note = ebay_auth_note(client_id="", client_secret="")
    assert "EBAY_CLIENT_ID" in note
    assert "EBAY_CLIENT_SECRET" in note
    assert EBAY_SIGNUP_URL in note
    assert "missing" in note
    page = EbayApiAdapter().discover(_query("dior"), None)
    assert page.outcome == SourceOutcome.AUTH_REQUIRED.value
    assert "EBAY_CLIENT_ID" in page.note
    assert EBAY_SIGNUP_URL in page.note
    assert page.note != "AUTH_REQUIRED"


def test_etsy_auth_names_key_and_signup_url() -> None:
    note = etsy_auth_note(api_key="")
    assert "ETSY_API_KEY" in note
    assert ETSY_SIGNUP_URL in note
    page = EtsyApiAdapter().discover(_query("dior"), None)
    assert page.outcome == SourceOutcome.AUTH_REQUIRED.value
    assert "ETSY_API_KEY" in page.note
    assert ETSY_SIGNUP_URL in page.note


def test_missing_key_note_lists_present_keys_separately() -> None:
    both = missing_key_note(
        key_names=("A", "B"),
        present={"A": "", "B": ""},
        signup_url="https://example.invalid/keys",
        product="Example API",
    )
    assert "A and B" in both
    one = missing_key_note(
        key_names=("A", "B"),
        present={"A": "set", "B": ""},
        signup_url="https://example.invalid/keys",
        product="Example API",
    )
    assert "missing B" in one
    assert "A and B" not in one


def test_recorded_disallow_blocks_search_when_live_robots_are_skipped() -> None:
    """Fails if AdmissionGate stops consulting recorded disallowed prefixes."""
    manifest = KindAdapter().manifest()
    assert "/search" in manifest.disallowed_path_prefixes
    http = HonestHttpClient()
    try:
        gate = AdmissionGate(RobotsCache(user_agent=http.user_agent), http)
        decision = gate.decide(
            "https://shop.kind.co.jp/search?q=prada",
            manifest,
            skip_live_robots=True,
        )
    finally:
        http.close()
    assert decision.allowed is False
    assert decision.outcome is SourceOutcome.BLOCKED_BY_POLICY
    assert path_matches_prefix(
        "https://shop.kind.co.jp/search?q=prada", list(manifest.disallowed_path_prefixes)
    )


def test_live_robots_block_search_when_recorded_disallow_is_empty() -> None:
    """Fails if AdmissionGate stops consulting the live robots body."""
    manifest = build_manifest(
        source_id="kind_robots_only",
        adapter="kind",
        domain="shop.kind.co.jp",
        access_method="http_get",
        admission_status=SourceAdmission.ADMITTED,
        allowed_use="product pages",
        disallowed_path_prefixes=[],
    )
    http = HonestHttpClient()
    try:
        gate = AdmissionGate(RobotsCache(user_agent=http.user_agent), http)
        decision = gate.decide(
            "https://shop.kind.co.jp/search?q=prada",
            manifest,
            robots_body="User-agent: *\nDisallow: /search\nAllow: /\n",
        )
    finally:
        http.close()
    assert decision.allowed is False
    assert decision.outcome is SourceOutcome.BLOCKED_BY_POLICY
    assert "robots" in decision.basis.lower()


def test_catalog_url_allowed_is_the_search_gate_even_without_spec_disallow() -> None:
    """Fails if catalog_url_allowed drops its hard-coded /search refuse."""
    search = "https://shop.kind.co.jp/search?q=prada"
    feed = "https://shop.kind.co.jp/products.json?limit=250&page=1"
    assert catalog_url_allowed(search, ()) is False
    assert catalog_url_allowed(feed, ()) is True
    requested: list[str] = []

    def fetch(url: str) -> bytes:
        requested.append(url)
        return b'{"products":[]}'

    result = page_catalog(
        origin="https://shop.kind.co.jp",
        feed_path="/search",
        query_texts=["personsoul"],
        fetch_page=fetch,
        disallowed=(),
        caps=CatalogCaps(4, 4, 4, 4),
        source_id="kind",
    )
    assert requested == []
    assert result.stopped_reason == "robots_disallowed"
    assert result.pages_read == 0


def test_query_slugs_do_not_invent_a_handle_for_japanese_only_text() -> None:
    assert query_slugs("ウィリーチャバリア") == []
