"""Normalization never destroys an original value."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.models import RawListing
from searcher.core.ids import sha256_hex
from searcher.core.time import parse_utc
from searcher.normalization.listing import normalize_raw, originals_preserved

_TS = parse_utc("2007-06-15T12:00:00+00:00")


@given(
    st.text(min_size=1, max_size=40),
    st.text(min_size=1, max_size=20),
    st.text(min_size=1, max_size=12),
)
def test_originals_survive_normalization(title: str, brand: str, size: str) -> None:
    raw = RawListing(
        source_adapter="generic_page",
        url="https://shop.example/products/x",
        payload={
            "title": title,
            "brand": brand,
            "size": size,
            "price_original": "12.00",
            "currency": "USD",
            "extraction_method": "dom",
        },
        content_digest=sha256_hex(title.encode("utf-8", errors="replace")),
        fetched_at=_TS,
    )
    candidate = normalize_raw(raw)
    assert candidate.field_records["title"].original == title
    assert candidate.field_records["brand"].original == brand
    assert candidate.field_records["size"].original == size
    assert originals_preserved(candidate)
    assert candidate.structured_data["originals"]["title"] == title
