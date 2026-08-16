"""A Shopify products.json feed expands into product candidates, never the index."""

from __future__ import annotations

import json
from pathlib import Path

from searcher.contracts.enums import DocumentClass
from searcher.sources.classify import classify_acquired_document, looks_like_index_url
from searcher.sources.expand import (
    IMAGES_MISSING_KEY,
    expand_index,
    expand_index_to_candidates,
    shopify_members_from_body,
)

INDEX_URL = "https://shop.kind.co.jp/collections/name-willy/products.json?limit=250"
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "shopify" / "name_willy_products.json"


def _body() -> bytes:
    return FIXTURE.read_bytes()


def test_shopify_products_json_is_an_index_not_a_product() -> None:
    body = _body()
    assert looks_like_index_url(INDEX_URL)
    assert (
        classify_acquired_document(url=INDEX_URL, body=body, listing_prefixes=("/products/",))
        is DocumentClass.INDEX
    )
    product_url = "https://shop.kind.co.jp/products/8001001141404"
    assert (
        classify_acquired_document(url=product_url, body=b"", listing_prefixes=("/products/",))
        is DocumentClass.PRODUCT
    )


def test_shopify_products_json_expands_to_one_candidate_per_product() -> None:
    body = _body()
    payload = json.loads(body.decode("utf-8"))
    expected = [item["handle"] for item in payload["products"]]
    candidates, receipt = expand_index_to_candidates(
        INDEX_URL,
        body,
        source_adapter="kind",
        listing_prefixes=("/products/",),
        per_index_cap=24,
        per_campaign_cap=48,
    )
    urls = [item.canonical_url for item in candidates]
    assert INDEX_URL not in urls
    assert not any("products.json" in url for url in urls)
    assert not any("/collections/" in url for url in urls)
    assert len(candidates) == len(expected)
    for handle in expected:
        assert any(url.endswith(f"/products/{handle}") for url in urls)
    by_url = {item.canonical_url: item for item in candidates}
    first = by_url["https://shop.kind.co.jp/products/8001001141404"]
    assert first.title is not None
    assert "ロングスリーブ" in str(first.title.value)
    assert first.images
    assert first.images[0].remote_url.endswith("8001001141404_1.jpg")
    assert receipt.members_found == len(expected)
    assert receipt.taken == len(expected)
    assert receipt.dropped == 0
    assert receipt.as_payload()["members_found"] == len(expected)


def test_index_url_itself_never_becomes_a_candidate() -> None:
    candidates, _receipt = expand_index_to_candidates(INDEX_URL, _body(), source_adapter="kind")
    assert candidates
    for candidate in candidates:
        assert candidate.canonical_url != INDEX_URL
        assert "products.json" not in candidate.canonical_url
        assert "/collections/" not in candidate.canonical_url


def test_expansion_caps_are_recorded_not_silent() -> None:
    body = _body()
    members = shopify_members_from_body(body, INDEX_URL, origin="https://shop.kind.co.jp")
    assert len(members) == 4
    result = expand_index(
        url=INDEX_URL,
        body=body,
        listing_prefixes=("/products/",),
        allowed_hosts=("shop.kind.co.jp",),
        per_index_cap=2,
        per_campaign_cap=10,
    )
    assert result.members_found == 4
    assert len(result.taken) == 2
    assert result.dropped == 2
    assert result.drop_reasons["per_index_cap"] == 2
    payload = result.as_payload()
    assert payload["members_found"] == 4
    assert payload["taken"] == 2
    assert payload["dropped"] == 2
    assert payload["drop_reasons"]["per_index_cap"] == 2


def test_adapters_do_not_parse_an_index_into_a_listing() -> None:
    from searcher.contracts.enums import SourceOutcome
    from searcher.contracts.models import FetchResult
    from searcher.core.ids import new_id, sha256_hex
    from searcher.sources.adapters.generic_page import GenericPageAdapter
    from searcher.sources.adapters.kind import KindAdapter
    from searcher.sources.fetch_modes import FetchedDocument

    body = _body()
    doc = FetchedDocument(
        result=FetchResult(
            attempt_id=new_id(),
            url=INDEX_URL,
            outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
            content_digest=sha256_hex(body),
            bytes=len(body),
            http_status=200,
            content_type="application/json",
        ),
        body=body,
        headers={"content-type": "application/json"},
        final_url=INDEX_URL,
    )
    assert GenericPageAdapter().parse(doc) == []
    assert KindAdapter().parse(doc) == []


def test_imageless_feed_member_records_why() -> None:
    candidates, _receipt = expand_index_to_candidates(INDEX_URL, _body(), source_adapter="kind")
    bare = [item for item in candidates if item.canonical_url.endswith("/products/8001001149999")]
    assert len(bare) == 1
    assert bare[0].images == []
    assert bare[0].structured_data.get(IMAGES_MISSING_KEY) == "feed_listed_no_images"
