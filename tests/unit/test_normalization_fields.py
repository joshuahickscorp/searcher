"""Normalization never drops the original representation."""

from __future__ import annotations

from searcher.contracts.enums import FactClass, FactOrigin
from searcher.contracts.models import RawListing
from searcher.core.ids import sha256_hex
from searcher.core.time import parse_utc
from searcher.normalization.listing import normalize_raw, originals_preserved


def test_originals_preserved_and_seller_not_observed() -> None:
    raw = RawListing(
        source_adapter="kind",
        url="https://shop.kind.co.jp/products/gat",
        payload={
            "title": "ディオールオム トレーナー",
            "brand": "Dior Homme",
            "price_original": "¥48,000",
            "currency": "JPY",
            "size": "26.5cm",
            "availability": "LIVE",
            "extraction_method": "json_ld",
        },
        content_digest=sha256_hex(b"x"),
        fetched_at=parse_utc("2007-06-15T12:00:00+00:00"),
    )
    candidate = normalize_raw(raw)
    assert candidate.field_records["title"].original == "ディオールオム トレーナー"
    assert candidate.field_records["price"].original == "¥48,000"
    assert candidate.currency_original == "JPY"
    assert candidate.size_original == "26.5cm"
    assert candidate.title is not None
    assert candidate.title.fact_class is FactClass.REPORTED_BY_SELLER
    assert candidate.title.origin is FactOrigin.SELLER
    assert originals_preserved(candidate)
