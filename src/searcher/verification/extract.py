"""Structured-data extraction for verification. Never guess from prose."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from searcher.contracts.enums import ExtractionMethod
from searcher.sources.adapters.generic_page import (
    extract_json_ld,
    extract_microdata,
    extract_open_graph,
)

try:
    from selectolax.parser import HTMLParser
except ImportError:  # pragma: no cover - selectolax is a hard dependency
    HTMLParser = None  # type: ignore[misc, assignment]


def extract_rdfa(html: str, url: str) -> dict[str, Any] | None:
    """RDFa Product block. Missing fields stay absent."""
    if HTMLParser is None:
        return None
    tree = HTMLParser(html)
    product = tree.css_first('[typeof*="Product"]')
    if product is None:
        return None

    def prop(name: str) -> str | None:
        node = product.css_first(f'[property="{name}"]') or product.css_first(
            f'[property$=":{name}"]'
        )
        if node is None:
            return None
        value = node.attributes.get("content") or node.text()
        return str(value).strip() if value else None

    title = prop("name")
    if not title:
        return None
    images: list[str] = []
    for node in product.css('[property="image"], [property$=":image"]'):
        src = (
            node.attributes.get("src")
            or node.attributes.get("content")
            or node.attributes.get("href")
            or node.attributes.get("resource")
        )
        if src:
            images.append(urljoin(url, src))
    seller = prop("seller") or prop("brand")
    return {
        "title": title,
        "description": prop("description"),
        "brand": prop("brand"),
        "seller": seller,
        "price_original": prop("price") or prop("lowPrice"),
        "currency": prop("priceCurrency"),
        "availability": prop("availability"),
        "images": images,
        "extraction_method": ExtractionMethod.RDFA.value,
    }


def _seller_of(payload: dict[str, Any]) -> str | None:
    for key in ("seller", "brand"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            name = value.get("name")
            if name:
                return str(name).strip()
    return None


def extract_structured(html: str, url: str) -> dict[str, Any] | None:
    """JSON-LD Product, then microdata, RDFa, Open Graph. No DOM guesswork."""
    for extractor in (extract_json_ld, extract_microdata, extract_rdfa, extract_open_graph):
        found = extractor(html, url)
        if not found:
            continue
        payload = dict(found)
        if not payload.get("seller"):
            seller = _seller_of(payload)
            if seller:
                payload["seller"] = seller
        return payload
    return None


def from_adapter_parse(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize an adapter parse payload into the verification field set."""
    seller = _seller_of(payload)
    images = payload.get("images") or []
    urls: list[str] = []
    if isinstance(images, list):
        for item in images:
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, dict):
                remote = item.get("url")
                if remote:
                    urls.append(str(remote))
    return {
        "title": payload.get("title"),
        "seller": seller,
        "brand": payload.get("brand"),
        "price_original": payload.get("price_original"),
        "currency": payload.get("currency"),
        "availability": payload.get("availability"),
        "images": urls,
        "extraction_method": payload.get("extraction_method") or ExtractionMethod.DOM.value,
    }
