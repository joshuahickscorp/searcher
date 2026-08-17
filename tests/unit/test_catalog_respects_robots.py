"""Catalogue fallback must never request a robots-disallowed /search path."""

from __future__ import annotations

from searcher.sources.adapters.kind import KindAdapter
from searcher.sources.adapters.product import KIND
from searcher.sources.catalog import (
    CatalogCaps,
    build_catalog_page_url,
    catalog_feed_path_of,
    catalog_url_allowed,
    page_catalog,
)
from searcher.sources.robots import path_matches_prefix


def test_kind_catalog_feed_is_not_search() -> None:
    path = catalog_feed_path_of(KIND)
    assert path is not None
    assert "/search" not in path
    url = build_catalog_page_url("https://shop.kind.co.jp", path, page=1)
    assert "/search" not in url
    assert url.endswith("/products.json") or "/products.json?" in url
    assert catalog_url_allowed(url, KIND.disallowed)


def test_kind_spec_disallows_search() -> None:
    assert "/search" in KIND.disallowed
    assert path_matches_prefix("https://shop.kind.co.jp/search?q=prada", list(KIND.disallowed))
    assert not path_matches_prefix(
        "https://shop.kind.co.jp/collections/all/products.json?limit=250&page=1",
        list(KIND.disallowed),
    )


def test_catalog_never_requests_search_when_feed_is_poisoned() -> None:
    requested: list[str] = []

    def fetch(url: str) -> bytes:
        requested.append(url)
        return b'{"products":[]}'

    result = page_catalog(
        origin="https://shop.kind.co.jp",
        feed_path="/search",
        query_texts=["Prada pump"],
        fetch_page=fetch,
        disallowed=KIND.disallowed,
        caps=CatalogCaps(4, 4, 4, 4),
        source_id="kind",
    )
    assert requested == []
    assert result.pages_read == 0
    assert result.stopped_reason == "robots_disallowed"
    assert result.drop_reasons.get("robots_disallowed", 0) >= 1
    assert all("/search" not in url for url in requested)


def test_catalog_url_allowed_is_the_search_guard() -> None:
    search = "https://shop.kind.co.jp/search?q=prada"
    catalog = "https://shop.kind.co.jp/collections/all/products.json?limit=250&page=1"
    assert catalog_url_allowed(search, KIND.disallowed) is False
    assert catalog_url_allowed(search, ()) is False
    assert catalog_url_allowed(catalog, KIND.disallowed) is True


def test_kind_discover_still_does_not_emit_search() -> None:
    from searcher.contracts.enums import QueryType
    from searcher.contracts.models import QueryVariant

    page = KindAdapter().discover(
        QueryVariant(
            query_id="q",
            hypothesis_id="h",
            round=0,
            language="en",
            query_text="Prada pump",
            query_type=QueryType.EXACT_NAME,
        ),
        None,
    )
    for url in page.urls:
        assert "/search" not in url
        assert catalog_url_allowed(url, KIND.disallowed)
