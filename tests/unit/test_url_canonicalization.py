"""URL canonicalization and listing-id extraction."""

from __future__ import annotations

from searcher.normalization.url import canonicalize_url, extract_listing_id
from searcher.sources.work_key import work_key


def test_strips_tracking_and_fragment() -> None:
    url = "https://WWW.Example.com/products/abc/?utm_source=x&fbclid=1&id=9#top"
    assert canonicalize_url(url) == "https://www.example.com/products/abc?id=9"


def test_default_port_dropped() -> None:
    assert canonicalize_url("https://shop.kind.co.jp:443/products/foo/") == (
        "https://shop.kind.co.jp/products/foo"
    )


def test_listing_id_from_common_shapes() -> None:
    assert extract_listing_id("https://www.ebay.com/itm/123456") == "123456"
    assert extract_listing_id("https://shop.kind.co.jp/products/dior-homme-gat") == "dior-homme-gat"


def test_work_key_is_stable() -> None:
    a = work_key(
        source_id="kind", kind="listing", target="https://shop.kind.co.jp/products/x?utm_source=1"
    )
    b = work_key(source_id="kind", kind="listing", target="https://shop.kind.co.jp/products/x")
    assert a == b
