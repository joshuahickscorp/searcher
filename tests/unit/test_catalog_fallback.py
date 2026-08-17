"""Catalogue fallback shortlists from the feed and honours page/product caps."""

from __future__ import annotations

import json
from pathlib import Path

from searcher.sources.catalog import (
    CatalogCaps,
    build_catalog_page_url,
    catalog_url_allowed,
    feed_text_matches,
    haystack_from_product,
    match_score,
    page_catalog,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "shopify"
ORIGIN = "https://shop.kind.co.jp"
FEED = "/collections/all/products.json"
PAGE_SIZE = 2


def _page_body(number: int) -> bytes:
    return (FIXTURES / f"catalog_page_{number}.json").read_bytes()


def _fetch_from(pages: dict[int, bytes], requested: list[str]):
    def fetch(url: str) -> bytes:
        requested.append(url)
        parsed_page = 1
        if "page=" in url:
            parsed_page = int(url.rsplit("page=", 1)[-1].split("&", 1)[0])
        return pages.get(parsed_page, b'{"products":[]}')

    return fetch


def _three_pages() -> dict[int, bytes]:
    return {1: _page_body(1), 2: _page_body(2), 3: _page_body(3)}


def test_only_feed_text_matches_are_promoted() -> None:
    requested: list[str] = []
    result = page_catalog(
        origin=ORIGIN,
        feed_path=FEED,
        query_texts=["Prada pump"],
        fetch_page=_fetch_from(_three_pages(), requested),
        disallowed=("/search",),
        page_size=PAGE_SIZE,
        caps=CatalogCaps(8, 8, 8, 8),
        allowed_hosts=("shop.kind.co.jp",),
        source_id="kind",
    )
    assert result.pages_read == 4
    assert result.products_seen == 6
    assert result.products_matched == 1
    assert result.products_promoted == 1
    assert result.promoted[0].handle == "8003001995070"
    assert result.promoted[0].url == "https://shop.kind.co.jp/products/8003001995070"
    assert result.drop_reasons["feed_text_no_match"] == 5
    assert result.dropped == 5
    assert result.as_payload()["products_promoted"] == 1
    assert "8003001995070" in result.as_payload()["member_urls"][0]
    assert all("/search" not in url for url in requested)


def test_page_cap_is_recorded_not_silent() -> None:
    requested: list[str] = []
    result = page_catalog(
        origin=ORIGIN,
        feed_path=FEED,
        query_texts=["Prada pump"],
        fetch_page=_fetch_from(_three_pages(), requested),
        page_size=PAGE_SIZE,
        caps=CatalogCaps(
            pages_per_source=2,
            pages_per_campaign=8,
            promote_per_source=8,
            promote_per_campaign=8,
        ),
        allowed_hosts=("shop.kind.co.jp",),
        source_id="kind",
    )
    assert result.pages_read == 2
    assert len(requested) == 2
    assert all("page=3" not in url for url in requested)
    assert result.products_seen == 4
    assert result.stopped_reason == "per_source_page_cap"
    assert result.pages_per_source_cap == 2
    assert result.as_payload()["stopped_reason"] == "per_source_page_cap"
    assert result.as_payload()["pages_read"] == 2


def test_campaign_page_cap_is_honoured() -> None:
    requested: list[str] = []
    result = page_catalog(
        origin=ORIGIN,
        feed_path=FEED,
        query_texts=["Prada pump"],
        fetch_page=_fetch_from(_three_pages(), requested),
        page_size=PAGE_SIZE,
        caps=CatalogCaps(
            pages_per_source=8,
            pages_per_campaign=4,
            promote_per_source=8,
            promote_per_campaign=8,
        ),
        campaign_pages_already=3,
        allowed_hosts=("shop.kind.co.jp",),
        source_id="kind",
    )
    assert result.pages_read == 1
    assert len(requested) == 1
    assert result.stopped_reason == "per_campaign_page_cap"
    assert result.campaign_pages_before == 3
    assert result.campaign_pages_after == 4


def test_product_cap_is_recorded_not_silent() -> None:
    requested: list[str] = []
    result = page_catalog(
        origin=ORIGIN,
        feed_path=FEED,
        query_texts=["Supreme"],
        fetch_page=_fetch_from(_three_pages(), requested),
        page_size=PAGE_SIZE,
        caps=CatalogCaps(
            pages_per_source=8,
            pages_per_campaign=8,
            promote_per_source=1,
            promote_per_campaign=8,
        ),
        allowed_hosts=("shop.kind.co.jp",),
        source_id="kind",
    )
    assert result.products_matched >= 2
    assert result.products_promoted == 1
    assert result.drop_reasons["per_source_promote_cap"] >= 1
    assert result.promote_per_source_cap == 1
    payload = result.as_payload()
    assert payload["products_promoted"] == 1
    assert payload["drop_reasons"]["per_source_promote_cap"] >= 1


def test_garbage_query_does_not_match_brand_tags() -> None:
    product = {
        "title": "デニムジャケット",
        "handle": "8106000031098",
        "vendor": "New Manual",
        "product_type": "ジャケット",
        "tags": "brand_PRADA:プラダ, date_20260816, Men, no, such",
        "variants": [{"price": "999", "available": True}],
        "images": [{"src": "https://cdn.example.test/x.jpg"}],
    }
    haystack = haystack_from_product(product)
    assert not feed_text_matches(["xyzzy-no-such-brand-999"], haystack)
    assert match_score(["xyzzy-no-such-brand-999"], haystack) == 0


def test_unknown_query_promotes_nothing() -> None:
    requested: list[str] = []
    result = page_catalog(
        origin=ORIGIN,
        feed_path=FEED,
        query_texts=["xyzzy-no-such-brand-999"],
        fetch_page=_fetch_from(_three_pages(), requested),
        page_size=PAGE_SIZE,
        caps=CatalogCaps(8, 8, 8, 8),
        allowed_hosts=("shop.kind.co.jp",),
        source_id="kind",
    )
    assert result.products_promoted == 0
    assert result.products_matched == 0
    assert result.promoted == []
    assert result.drop_reasons["feed_text_no_match"] == result.products_seen


def test_source_without_feed_does_not_page() -> None:
    requested: list[str] = []
    result = page_catalog(
        origin=ORIGIN,
        feed_path="",
        query_texts=["Prada pump"],
        fetch_page=_fetch_from(_three_pages(), requested),
        caps=CatalogCaps(8, 8, 8, 8),
        source_id="komehyo",
    )
    assert requested == []
    assert result.stopped_reason == "no_catalog_feed"
    assert result.pages_read == 0


def test_feed_match_is_not_identity() -> None:
    product = json.loads(_page_body(2).decode("utf-8"))["products"][0]
    haystack = haystack_from_product(product)
    assert feed_text_matches(["Prada pump"], haystack)
    assert match_score(["Prada pump"], haystack) >= 1
    assert "identity" not in haystack
    assert product.get("item_match") is None


def test_catalog_urls_use_page_param() -> None:
    url = build_catalog_page_url(ORIGIN, FEED, page=2, page_size=250)
    assert url.startswith("https://shop.kind.co.jp/collections/all/products.json?")
    assert "limit=250" in url
    assert "page=2" in url
    assert catalog_url_allowed(url, ("/search",))
