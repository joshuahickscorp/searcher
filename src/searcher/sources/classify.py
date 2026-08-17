"""Classify an acquired document before it may become a candidate.

A candidate is one specific item at one URL. Collection pages, search
results, sitemaps, and product feeds are indexes: they are expanded, never
stored as the item they list.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlparse

from searcher.contracts.enums import DocumentClass
from searcher.sources.platform import maybe_decompress

_PRODUCT_PATH = re.compile(
    r"/(?:products?|listing|listings|items?|itm|c/goods)/[^/]+/?(?:\.json)?$",
    re.I,
)
_COLLECTION_PRODUCT = re.compile(r"/collections/[^/]+/products/[^/]+/?(?:\.json)?$", re.I)
_JSON_LD_SCRIPT = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
_INDEX_PATH_PARTS = (
    "/collections/",
    "/category/",
    "/categories/",
    "/search",
    "/catalog",
    "/designers/",
)


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def try_json(body: bytes) -> Any:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8-sig", errors="replace"))
    except json.JSONDecodeError:
        return None


def looks_like_index_url(url: str) -> bool:
    """True when the URL itself names a feed, collection, search, or sitemap."""
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")
    lowered = url.lower()
    if "sitemap" in path or "sitemap" in lowered:
        return True
    if path.endswith("/products.json") or path.endswith("products.json"):
        return True
    if "/search" in path or path.endswith("/search"):
        return True
    if _COLLECTION_PRODUCT.search(path):
        return False
    if "/collections/" in path:
        return True
    return any(part in path for part in ("/category/", "/categories/"))


def looks_like_product_url(url: str, listing_prefixes: Sequence[str] = ()) -> bool:
    parsed = urlparse(url)
    path = parsed.path
    if looks_like_index_url(url):
        return False
    if listing_prefixes and any(prefix in path for prefix in listing_prefixes):
        return True
    if _COLLECTION_PRODUCT.search(path):
        return True
    return bool(_PRODUCT_PATH.search(path))


def _ld_blocks(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for match in _JSON_LD_SCRIPT.finditer(text):
        try:
            loaded = json.loads(match.group(1))
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


def _type_names(block: dict[str, Any]) -> list[str]:
    raw = block.get("@type")
    if isinstance(raw, list):
        return [str(item).lower() for item in raw if item]
    if raw:
        return [str(raw).lower()]
    return []


def _json_ld_class(body: bytes) -> DocumentClass | None:
    text = body.decode("utf-8-sig", errors="replace")
    if "ld+json" not in text.lower() and '"@type"' not in text:
        return None
    blocks = _ld_blocks(text)
    if not blocks:
        payload = try_json(body)
        if isinstance(payload, dict):
            blocks = [payload]
        elif isinstance(payload, list):
            blocks = [item for item in payload if isinstance(item, dict)]
    product = False
    index = False
    for block in blocks:
        names = _type_names(block)
        if any(name.endswith("product") and "productgroup" not in name for name in names):
            product = True
        if any(
            token in name
            for name in names
            for token in (
                "itemlist",
                "collectionpage",
                "searchresultspage",
                "offercatalog",
            )
        ):
            index = True
    if product and not index:
        return DocumentClass.PRODUCT
    if index:
        return DocumentClass.INDEX
    return None


def _shopify_payload_class(payload: Any) -> DocumentClass | None:
    if not isinstance(payload, dict):
        return None
    products = payload.get("products")
    product = payload.get("product")
    if isinstance(products, list):
        return DocumentClass.INDEX
    if isinstance(product, dict):
        return DocumentClass.PRODUCT
    return None


def _looks_like_sitemap(body: bytes, content_type: str | None) -> bool:
    head = body.lstrip()[:400].lower()
    ctype = (content_type or "").lower()
    if "xml" in ctype and (b"<urlset" in head or b"<sitemapindex" in head):
        return True
    return b"<urlset" in head or b"<sitemapindex" in head


# A page can say 404 in its title and body while the transport says 200. Sellers
# and shop platforms do this constantly for removed listings. The URL still looks
# like a product URL, so URL shape - which otherwise correctly wins over a
# misleading body - classifies the error page as a product, and every adapter
# below then manufactures a listing out of it. That puts a page which is not a
# listing into the candidate pool as though it were one.
_SOFT_ERROR_MARKERS = (
    "404 not found",
    "page not found",
    "404 - not found",
    "not found",
    "410 gone",
    "no longer available",
    "this listing has ended",
    "sorry, this page",
)


def looks_like_soft_error(body: bytes) -> bool:
    """True when the body announces an error the status line did not."""
    if not body:
        return False
    head = body[:4096].decode("utf-8", errors="replace").lower()
    title = ""
    start = head.find("<title")
    if start != -1:
        opened = head.find(">", start)
        closed = head.find("</title", opened + 1) if opened != -1 else -1
        if opened != -1 and closed != -1:
            title = head[opened + 1 : closed].strip()
    if any(marker in title for marker in _SOFT_ERROR_MARKERS):
        return True
    # Outside the title, require an error phrase in a short body: a long page
    # mentioning "not found" in passing is not an error page.
    if len(head) < 1200:
        return any(marker in head for marker in _SOFT_ERROR_MARKERS[:6])
    return False


def classify_acquired_document(
    *,
    url: str,
    body: bytes = b"",
    content_type: str | None = None,
    listing_prefixes: Sequence[str] = (),
) -> DocumentClass:
    """Return product, index, or other. URL shape wins over a misleading body."""
    if body:
        body = maybe_decompress(body)
    if looks_like_soft_error(body):
        return DocumentClass.OTHER
    if looks_like_index_url(url):
        payload = try_json(body)
        shopify = _shopify_payload_class(payload)
        if shopify is DocumentClass.PRODUCT:
            return DocumentClass.PRODUCT
        return DocumentClass.INDEX
    if looks_like_product_url(url, listing_prefixes):
        payload = try_json(body)
        shopify = _shopify_payload_class(payload)
        if shopify is DocumentClass.INDEX:
            return DocumentClass.INDEX
        return DocumentClass.PRODUCT
    if _looks_like_sitemap(body, content_type):
        return DocumentClass.INDEX
    payload = try_json(body)
    shopify = _shopify_payload_class(payload)
    if shopify is not None:
        return shopify
    ld = _json_ld_class(body)
    if ld is not None:
        return ld
    path = urlparse(url).path.lower()
    if any(part in path for part in _INDEX_PATH_PARTS):
        return DocumentClass.INDEX
    return DocumentClass.OTHER
