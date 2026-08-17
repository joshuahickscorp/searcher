"""Uncredentialed reach is a platform shape, not a per-shop integration."""

from __future__ import annotations

import gzip
import os

from searcher.contracts.enums import QueryType, SourceAdmission, SourceOutcome
from searcher.contracts.models import QueryVariant
from searcher.sources.adapters import resolve_adapter
from searcher.sources.adapters.byronesque import ByronesqueAdapter
from searcher.sources.adapters.ebay_api import EbayApiAdapter
from searcher.sources.adapters.etsy_api import EtsyApiAdapter
from searcher.sources.adapters.kind import KindAdapter
from searcher.sources.adapters.product import BYRONESQUE, KIND, REBAG, SourceSpec
from searcher.sources.adapters.rebag import RebagAdapter
from searcher.sources.adapters.searx import SearxAdapter
from searcher.sources.broker import DEFAULT_ORDER, SourceBroker
from searcher.sources.catalog import catalog_feed_path_of
from searcher.sources.expand import expand_index, extract_index_members
from searcher.sources.platform import (
    SHOPIFY_FEED_PATH,
    WOOCOMMERCE_STORE_API,
    commerce_origins_for,
    inferred_catalog_feed_path,
    inferred_sitemap_urls,
    requires_operator_credential,
    strategy_origins_for,
)
from searcher.sources.strategies import CATALOG_FEED, COLLECTION_SLUG, SITEMAP, plan_strategies


def _query(text: str = "Prada nylon") -> QueryVariant:
    return QueryVariant(
        query_id="q",
        hypothesis_id="h",
        round=1,
        language="en",
        query_text=text,
        query_type=QueryType.EXACT_NAME,
    )


def _shopify_shaped(*, domain: str = "www.example.com", origin: str | None = None) -> SourceSpec:
    return SourceSpec(
        source_id="shaped",
        adapter="shaped",
        domain=domain,
        access_method="http_get",
        admission=SourceAdmission.ADMITTED,
        allowed_use="public product pages",
        source_class="consignment",
        robots_policy="fetched",
        languages=("en",),
        disallowed=("/search",),
        listing_prefixes=("/products/",),
        origin=origin,
    )


def test_shopify_shape_infers_products_json_without_a_per_shop_feed_path() -> None:
    spec = _shopify_shaped()
    assert spec.catalog_feed_path is None
    assert inferred_catalog_feed_path(spec) == SHOPIFY_FEED_PATH
    assert catalog_feed_path_of(spec) == SHOPIFY_FEED_PATH
    assert catalog_feed_path_of(KIND) == "/products.json"
    assert catalog_feed_path_of(REBAG) == SHOPIFY_FEED_PATH


def test_shop_dot_host_is_a_commerce_origin_for_www_shopify_shops() -> None:
    spec = _shopify_shaped(domain="www.rebag.com")
    origins = commerce_origins_for(spec)
    assert "https://www.rebag.com" in origins
    assert "https://shop.rebag.com" in origins
    strategy = strategy_origins_for(REBAG)
    assert strategy[0] == "https://shop.rebag.com"
    assert "https://www.rebag.com" in strategy
    sitemaps = inferred_sitemap_urls(REBAG)
    assert "https://shop.rebag.com/sitemap.xml" in sitemaps


def test_loopback_fixture_does_not_invent_a_shop_subdomain() -> None:
    spec = _shopify_shaped(domain="127.0.0.1:9", origin="http://127.0.0.1:9")
    origins = commerce_origins_for(spec)
    assert origins == ("http://127.0.0.1:9",)
    assert all("shop.127" not in item for item in origins)


def test_rebag_and_kind_queue_the_same_catalog_and_sitemap_strategies() -> None:
    for spec in (KIND, REBAG, RebagAdapter().spec, KindAdapter().spec):
        planned = plan_strategies(spec, "Prada nylon")
        by_name = {item.name: item for item in planned}
        assert CATALOG_FEED in by_name
        assert SITEMAP in by_name
        assert by_name[CATALOG_FEED].status == "queued"
        assert any("/products.json" in url for url in by_name[CATALOG_FEED].urls)
        assert by_name[SITEMAP].status == "queued"
        assert any("sitemap" in url for url in by_name[SITEMAP].urls)
        assert all("/search" not in url for item in planned for url in item.urls)


def test_woocommerce_store_api_is_not_inferred() -> None:
    assert catalog_feed_path_of(BYRONESQUE) is None
    assert inferred_catalog_feed_path(BYRONESQUE) is None
    planned = plan_strategies(ByronesqueAdapter().spec, "Margiela jacket")
    catalog = next(item for item in planned if item.name == CATALOG_FEED)
    assert catalog.status == "skipped"
    assert all(WOOCOMMERCE_STORE_API not in url for item in planned for url in item.urls)


def test_disallowed_generic_feed_is_blocked_with_a_rule() -> None:
    spec = _shopify_shaped()
    spec = SourceSpec(
        source_id=spec.source_id,
        adapter=spec.adapter,
        domain=spec.domain,
        access_method=spec.access_method,
        admission=spec.admission,
        allowed_use=spec.allowed_use,
        source_class=spec.source_class,
        robots_policy=spec.robots_policy,
        languages=spec.languages,
        disallowed=("/products.json", "/search"),
        listing_prefixes=spec.listing_prefixes,
        origin=spec.origin,
    )
    planned = plan_strategies(spec, "Prada")
    catalog = next(item for item in planned if item.name == CATALOG_FEED)
    assert catalog.status == "blocked"
    assert "disallow" in catalog.reason.lower() or "disallowed" in catalog.reason.lower()


def test_sitemap_index_children_are_kept_and_gzip_bodies_parse() -> None:
    index = (
        b"<?xml version='1.0'?><sitemapindex>"
        b"<loc>https://shop.example.com/sitemap_products_1.xml</loc>"
        b"<loc>https://shop.example.com/sitemap_pages_1.xml</loc>"
        b"</sitemapindex>"
    )
    members = extract_index_members(
        url="https://shop.example.com/sitemap.xml",
        body=index,
        listing_prefixes=("/products/",),
        allowed_hosts=("shop.example.com",),
    )
    urls = [item.url for item in members]
    assert "https://shop.example.com/sitemap_products_1.xml" in urls
    assert urls[0].endswith("sitemap_products_1.xml")

    inner = (
        b"<?xml version='1.0'?><urlset>"
        b"<loc>https://shop.example.com/products/prada-nylon</loc>"
        b"<loc>https://shop.example.com/products/other</loc>"
        b"</urlset>"
    )
    compressed = gzip.compress(inner)
    result = expand_index(
        url="https://shop.example.com/sitemap_products_1.xml.gz",
        body=compressed,
        listing_prefixes=("/products/",),
        allowed_hosts=("shop.example.com",),
        query_texts=["prada nylon"],
    )
    taken = [item.url for item in result.taken]
    assert "https://shop.example.com/products/prada-nylon" in taken
    assert all("sitemap" not in url for url in taken)


def test_default_live_plan_does_not_require_a_credential() -> None:
    previous = os.environ.get("SEARCHER_SEARX_URL")
    os.environ.pop("SEARCHER_SEARX_URL", None)
    try:
        plans = SourceBroker().plan([_query()])
    finally:
        if previous is None:
            os.environ.pop("SEARCHER_SEARX_URL", None)
        else:
            os.environ["SEARCHER_SEARX_URL"] = previous
    names = [plan.source_adapter for plan in plans]
    assert names
    assert "ebay" not in names
    assert "etsy" not in names
    assert "searx" in names
    for name in names:
        adapter = SourceBroker().manifest_of(name)
        assert requires_operator_credential(adapter) is False
        page = resolve_adapter(name).discover(_query(), None)
        assert page.outcome != SourceOutcome.AUTH_REQUIRED.value


def test_key_gated_adapters_say_they_are_outside_uncredentialed_reach() -> None:
    assert requires_operator_credential(EbayApiAdapter().manifest()) is True
    assert requires_operator_credential(EtsyApiAdapter().manifest()) is True
    assert requires_operator_credential(SearxAdapter(endpoint="").manifest()) is False
    assert requires_operator_credential(KindAdapter().manifest()) is False
    ebay = EbayApiAdapter().discover(_query(), None)
    etsy = EtsyApiAdapter().discover(_query(), None)
    assert ebay.outcome == SourceOutcome.AUTH_REQUIRED.value
    assert etsy.outcome == SourceOutcome.AUTH_REQUIRED.value
    assert "not part of uncredentialed reach" in ebay.note.lower()
    assert "not part of uncredentialed reach" in etsy.note.lower()


def test_searx_absent_is_optional_not_a_hard_failure() -> None:
    adapter = SearxAdapter(endpoint="")
    page = adapter.discover(_query(), None)
    assert page.outcome == SourceOutcome.SOURCE_UNAVAILABLE.value
    assert "SEARCHER_SEARX_URL" in page.note
    names = list(DEFAULT_ORDER)
    assert names[0] == "searx"
    assert "ebay" in names
    assert "etsy" in names


def test_collection_slug_is_inferred_for_a_shopify_shaped_shop() -> None:
    spec = _shopify_shaped(domain="www.example.com")
    planned = plan_strategies(spec, "Prada nylon")
    collection = next(item for item in planned if item.name == COLLECTION_SLUG)
    assert collection.status == "queued"
    assert any("/collections/" in url and "products.json" in url for url in collection.urls)
    assert any("shop.example.com" in url for url in collection.urls)
