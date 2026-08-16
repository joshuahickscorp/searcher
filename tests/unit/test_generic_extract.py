"""JSON-LD first extraction does not invent fields."""

from __future__ import annotations

from searcher.sources.adapters.generic_page import extract_listing

HTML = """
<html><head>
<script type="application/ld+json">
{"@type":"Product","name":"Dior Homme Army Trainer","brand":{"name":"Dior Homme"},
 "offers":{"price":"48000","priceCurrency":"JPY","availability":"https://schema.org/InStock"},
 "image":"https://shop.example/img.jpg"}
</script>
<meta property="og:title" content="should not win">
</head><body><h1>visible</h1></body></html>
"""


def test_json_ld_wins_and_missing_size_is_absent() -> None:
    payload = extract_listing(HTML, "https://shop.example/products/gat")
    assert payload["title"] == "Dior Homme Army Trainer"
    assert payload["brand"] == "Dior Homme"
    assert payload["price_original"] == "48000"
    assert payload["currency"] == "JPY"
    assert payload["extraction_method"] == "json_ld"
    assert "size" not in payload or payload.get("size") in (None, "")
