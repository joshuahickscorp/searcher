"""§14.4 generic page adapter: JSON-LD, microdata, Open Graph, visible DOM."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

from searcher.contracts.enums import (
    DocumentClass,
    ExtractionMethod,
    FetchMode,
    SourceAdmission,
    SourceOutcome,
)
from searcher.contracts.models import (
    ListingCandidate,
    LiveStatus,
    QueryVariant,
    RawListing,
    SourceHealth,
    SourceManifest,
)
from searcher.core.ids import sha256_hex
from searcher.core.time import utc_now
from searcher.normalization.html import strip_html
from searcher.normalization.listing import normalize_raw
from searcher.sources.adapters.protocol import DiscoveryPageResult
from searcher.sources.classify import classify_acquired_document
from searcher.sources.expand import IMAGES_MISSING_KEY, attach_image_absence
from searcher.sources.fetch_modes import FetchedDocument
from searcher.sources.live_check import classify_liveness
from searcher.sources.manifest import build_manifest

try:
    from selectolax.parser import HTMLParser
except ImportError:  # pragma: no cover - exercised when the extra is missing
    HTMLParser = None  # type: ignore[misc, assignment]


def _parser(html: str) -> Any:
    if HTMLParser is None:
        raise RuntimeError("selectolax is required for HTML parsing")
    return HTMLParser(html)


def classify_page_type(html: str, url: str) -> str:
    document = classify_acquired_document(url=url, body=html.encode("utf-8", errors="replace"))
    if document is DocumentClass.INDEX:
        if "search" in url.lower():
            return "search"
        return "collection"
    if document is DocumentClass.PRODUCT:
        return "product"
    return "unknown"


def _json_ld_blocks(tree: Any) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text() or ""
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, list):
            blocks.extend(item for item in loaded if isinstance(item, dict))
        elif isinstance(loaded, dict):
            graph = loaded.get("@graph")
            if isinstance(graph, list):
                blocks.extend(item for item in graph if isinstance(item, dict))
            else:
                blocks.append(loaded)
    return blocks


def _product_from_json_ld(blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
    for block in blocks:
        types = block.get("@type")
        names = types if isinstance(types, list) else [types]
        if any(str(name).lower().endswith("product") for name in names if name):
            return block
    return None


def _offer_fields(product: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    offers = product.get("offers")
    if isinstance(offers, list) and offers:
        offers = offers[0]
    if not isinstance(offers, dict):
        return None, None, None
    price = offers.get("price") or offers.get("lowPrice")
    currency = offers.get("priceCurrency")
    availability = offers.get("availability")
    return (
        str(price) if price is not None else None,
        str(currency) if currency else None,
        str(availability) if availability else None,
    )


def _images_of(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        url = value.get("url") or value.get("contentUrl")
        return [str(url)] if url else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_images_of(item))
        return out
    return []


def extract_json_ld(html: str, url: str) -> dict[str, Any] | None:
    tree = _parser(html)
    product = _product_from_json_ld(_json_ld_blocks(tree))
    if product is None:
        return None
    price, currency, availability = _offer_fields(product)
    brand = product.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    images = _images_of(product.get("image"))
    return {
        "title": product.get("name"),
        "description": product.get("description"),
        "brand": brand,
        "model": product.get("model") or product.get("sku"),
        "price_original": price,
        "currency": currency,
        "availability": availability,
        "images": images,
        "listing_id": product.get("sku") or product.get("productID"),
        "extraction_method": ExtractionMethod.JSON_LD.value,
    }


def extract_microdata(html: str, url: str) -> dict[str, Any] | None:
    tree = _parser(html)
    product = tree.css_first('[itemtype*="Product"]')
    if product is None:
        return None

    def prop(name: str) -> str | None:
        node = product.css_first(f'[itemprop="{name}"]')
        if node is None:
            return None
        value = node.attributes.get("content") or node.text()
        return str(value) if value else None

    images = []
    for node in product.css('[itemprop="image"]'):
        src = (
            node.attributes.get("src")
            or node.attributes.get("content")
            or node.attributes.get("href")
        )  # noqa: E501
        if src:
            images.append(urljoin(url, src))
    title = prop("name")
    if not title:
        return None
    return {
        "title": title,
        "description": prop("description"),
        "brand": prop("brand"),
        "price_original": prop("price"),
        "currency": prop("priceCurrency"),
        "availability": prop("availability"),
        "images": images,
        "extraction_method": ExtractionMethod.MICRODATA.value,
    }


def extract_open_graph(html: str, url: str) -> dict[str, Any] | None:
    tree = _parser(html)

    def og(name: str) -> str | None:
        node = tree.css_first(f'meta[property="{name}"]') or tree.css_first(f'meta[name="{name}"]')
        if node is None:
            return None
        value = node.attributes.get("content")
        return str(value) if value else None

    title = og("og:title")
    if not title:
        return None
    images = [og("og:image")] if og("og:image") else []
    return {
        "title": title,
        "description": og("og:description"),
        "price_original": og("product:price:amount") or og("og:price:amount"),
        "currency": og("product:price:currency") or og("og:price:currency"),
        "images": [urljoin(url, img) for img in images if img],
        "extraction_method": ExtractionMethod.OPEN_GRAPH.value,
    }


def extract_dom(html: str, url: str) -> dict[str, Any]:
    tree = _parser(html)
    h1 = tree.css_first("h1")
    title = h1.text() if h1 is not None else None
    desc_node = tree.css_first('meta[name="description"]')
    description = desc_node.attributes.get("content") if desc_node is not None else None
    price_node = (
        tree.css_first('[itemprop="price"]')
        or tree.css_first(".price")
        or tree.css_first(".product-price")
    )
    price = None
    if price_node is not None:
        price = price_node.attributes.get("content") or price_node.text()
    images: list[str] = []
    for node in tree.css("img"):
        src = node.attributes.get("src") or node.attributes.get("data-src")
        if src and not src.startswith("data:"):
            images.append(urljoin(url, src))
        if len(images) >= 8:
            break
    return {
        "title": strip_html(title) if title else None,
        "description": strip_html(description) if description else None,
        "price_original": strip_html(price) if price else None,
        "images": images,
        "extraction_method": ExtractionMethod.DOM.value,
    }


def extract_listing(html: str, url: str) -> dict[str, Any]:
    """Prefer structured data. Never fabricate a missing field."""
    page_type = classify_page_type(html, url)
    merged: dict[str, Any] = {"page_type": page_type, "canonical_url": url}
    for extractor in (extract_json_ld, extract_microdata, extract_open_graph):
        found = extractor(html, url)
        if not found:
            continue
        for key, value in found.items():
            if value in (None, "", [], {}) and key in merged:
                continue
            if key == "images":
                existing = list(merged.get("images") or [])
                for image in value or []:
                    if image not in existing:
                        existing.append(image)
                merged["images"] = existing
                continue
            if key not in merged or merged[key] in (None, ""):
                merged[key] = value
        if merged.get("extraction_method") is None:
            merged["extraction_method"] = found.get("extraction_method")
    dom = extract_dom(html, url)
    for key, value in dom.items():
        if key == "images":
            existing = list(merged.get("images") or [])
            for image in value or []:
                if image not in existing:
                    existing.append(image)
            merged["images"] = existing
            continue
        if key not in merged or merged[key] in (None, ""):
            merged[key] = value
    if "extraction_method" not in merged:
        merged["extraction_method"] = ExtractionMethod.DOM.value
    # Vision hook is present and unused.
    merged["vision_fallback"] = None
    return merged


def listing_links(html: str, url: str, prefixes: list[str]) -> list[str]:
    tree = _parser(html)
    found: list[str] = []
    for node in tree.css("a[href]"):
        href = node.attributes.get("href")
        if not href:
            continue
        absolute = urljoin(url, href)
        if prefixes and not any(part in absolute for part in prefixes):
            continue
        if absolute not in found:
            found.append(absolute)
    return found


class GenericPageAdapter:
    def __init__(self, manifest: SourceManifest | None = None) -> None:
        self._manifest = manifest or build_manifest(
            source_id="generic_page",
            adapter="generic_page",
            domain="*",
            access_method="http_get",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="public product page parse",
            source_class="user_url",
            capabilities=["listing_fetch"],
        )

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        return SourceHealth(
            source_id=self._manifest.source_id,
            last_outcome=SourceOutcome.NOT_ATTEMPTED,
            last_checked_at=utc_now(),
        )

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del query, cursor
        return DiscoveryPageResult(
            [], [], None, SourceOutcome.NOT_ATTEMPTED.value, "generic has no search"
        )  # noqa: E501

    def fetch(self, url: str, mode: FetchMode) -> FetchedDocument:
        del url, mode
        raise RuntimeError("GenericPageAdapter.fetch requires an Escalator; use the engine")

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        if fetch.result.outcome is not SourceOutcome.SEARCHED_MATCHES_FOUND:
            return []
        url = fetch.final_url or fetch.result.url
        prefixes = list(self._manifest.listing_path_prefixes)
        document = classify_acquired_document(
            url=url,
            body=fetch.body,
            content_type=fetch.result.content_type,
            listing_prefixes=prefixes,
        )
        if document is not DocumentClass.PRODUCT:
            return []
        html = fetch.body.decode("utf-8", errors="replace")
        payload = extract_listing(html, url)
        payload["images"] = [{"url": img} for img in payload.get("images") or []]
        if not payload["images"]:
            payload[IMAGES_MISSING_KEY] = "page_extracted_no_images"
        return [
            RawListing(
                source_adapter=self._manifest.adapter,
                url=url,
                payload=payload,
                content_digest=fetch.result.content_digest or sha256_hex(fetch.body),
                fetched_at=utc_now(),
            )
        ]

    def normalize(self, raw: RawListing) -> ListingCandidate:
        return attach_image_absence(normalize_raw(raw), raw)

    def live_check(self, candidate: ListingCandidate) -> LiveStatus:
        return classify_liveness(
            http_status=None,
            body="",
            outcome=SourceOutcome.NOT_ATTEMPTED,
        )

    def vision_fallback(self, html: str, url: str) -> None:
        """Hook only. Screenshot-plus-vision is out of scope."""
        del html, url
        return None
