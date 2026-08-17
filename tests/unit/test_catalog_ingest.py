"""Catalogue ingest: fill the shelf the descriptor search reads from.

The warm index is a cache of past text searches - populated from candidates a
campaign already retrieved - so a listing no query ever named was never indexed.
Visual retrieval works and searches an empty shelf. This indexes a source's
products independently of any query, which is the only route to an item whose
listing carries no distinguishing text.
"""

from __future__ import annotations

from typing import Any

from searcher.index.ingest import ingest_products


def _product(handle: str, images: int = 2) -> dict[str, Any]:
    return {
        "handle": handle,
        "title": f"title {handle}",
        "images": [{"src": f"https://example.test/{handle}/{i}.jpg"} for i in range(images)],
    }


def _ok_fetch(url: str) -> bytes:
    return url.encode()


def _ok_describe(data: bytes) -> list[float]:
    return [float(len(data)), 1.0, 0.0]


def test_every_product_with_a_describable_image_is_indexed() -> None:
    stored: dict[str, dict[str, list[float]]] = {}

    def put(product: dict[str, Any], descriptors: dict[str, list[float]]) -> None:
        stored[str(product["handle"])] = descriptors

    report = ingest_products(
        [_product("a"), _product("b")],
        put_listing=put,
        fetch_image=_ok_fetch,
        describe=_ok_describe,
    )
    assert report.listings_indexed == 2
    assert set(stored) == {"a", "b"}
    assert report.images_described == 4


def test_a_product_with_no_images_is_skipped_and_counted() -> None:
    report = ingest_products(
        [{"handle": "bare", "images": []}],
        put_listing=lambda p, d: None,
        fetch_image=_ok_fetch,
        describe=_ok_describe,
    )
    assert report.listings_indexed == 0
    assert report.skipped_no_images == 1


def test_a_product_whose_images_yield_no_descriptor_is_not_indexed() -> None:
    """Indexing a listing with no descriptor would put it beyond visual reach."""
    report = ingest_products(
        [_product("a")],
        put_listing=lambda p, d: None,
        fetch_image=_ok_fetch,
        describe=lambda data: None,
    )
    assert report.listings_indexed == 0
    assert report.skipped_no_descriptor == 1


def test_one_bad_image_does_not_stop_the_catalogue() -> None:
    """A walk that dies on the first broken image indexes almost nothing."""
    calls = {"n": 0}

    def flaky(url: str) -> bytes:
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("slow image")
        return url.encode()

    report = ingest_products(
        [_product("a"), _product("b")],
        put_listing=lambda p, d: None,
        fetch_image=flaky,
        describe=_ok_describe,
    )
    assert report.listings_indexed == 2, "the walk continued past a failed fetch"
    assert any("fetch" in err for err in report.errors)


def test_an_indexing_failure_is_recorded_and_the_walk_continues() -> None:
    def explode(product: dict[str, Any], descriptors: dict[str, list[float]]) -> None:
        if product["handle"] == "a":
            raise RuntimeError("db busy")

    report = ingest_products(
        [_product("a"), _product("b")],
        put_listing=explode,
        fetch_image=_ok_fetch,
        describe=_ok_describe,
    )
    assert report.listings_indexed == 1
    assert any("index a" in err for err in report.errors)


def test_only_the_first_few_images_are_described() -> None:
    """A listing is found by whichever photograph matches; the tenth costs more."""
    report = ingest_products(
        [_product("a", images=10)],
        put_listing=lambda p, d: None,
        fetch_image=_ok_fetch,
        describe=_ok_describe,
        max_images_per_product=3,
    )
    assert report.images_described == 3


def test_the_report_is_checkable_rather_than_a_boolean() -> None:
    report = ingest_products(
        [_product("a"), {"handle": "bare", "images": []}],
        put_listing=lambda p, d: None,
        fetch_image=_ok_fetch,
        describe=_ok_describe,
    )
    payload = report.as_payload()
    assert payload["products_seen"] == 2
    assert payload["listings_indexed"] == 1
    assert payload["skipped_no_images"] == 1
