"""Recognise common commerce-platform shapes from public, key-free paths.

A Shopify storefront publishes `/products.json` and a `/sitemap.xml` index.
Those paths are the same on every shop of that shape. This module infers them
from the recorded spec (and from the `shop.` host convention) so each admitted
shop gets the feed, sitemap, and catalogue walk without a bespoke adapter.

Auth-gated store APIs (WooCommerce REST, official marketplace APIs) are not
inferred. A path that exists but robots or the server refuse is a blocked
source with a stated rule, not a silent miss.
"""

from __future__ import annotations

import gzip
from collections.abc import Sequence
from urllib.parse import urlparse

SHOPIFY_FEED_PATH = "/products.json"
SHOPIFY_COLLECTION_FEED = "/collections/{slug}/products.json?limit=250"
SHOPIFY_SITEMAP_PATH = "/sitemap.xml"
SHOPIFY_ROBOTS_TOKEN = "shopify"

# Predictable but typically credentialed. Never inferred; only used if a spec
# already declared the path, and a 401 is reported as blocked-with-rule.
WOOCOMMERCE_STORE_API = "/wp-json/wc/store/v1/products"

_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})
_PRIVATE_SUFFIXES = (".invalid", ".test", ".localhost", ".local")


def origin_for_spec(spec: object, fallback: str = "") -> str:
    explicit = getattr(spec, "origin", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().rstrip("/")
    domain = getattr(spec, "domain", None)
    if isinstance(domain, str) and domain.strip():
        return f"https://{domain.strip()}"
    return fallback.rstrip("/") if fallback else ""


def _hostname(origin: str) -> str:
    return (urlparse(origin).hostname or "").lower()


def _is_public_hostname(host: str) -> bool:
    if not host or host in _LOOPBACK:
        return False
    return not any(host.endswith(suffix) for suffix in _PRIVATE_SUFFIXES)


def _listing_prefixes(spec: object) -> tuple[str, ...]:
    raw = getattr(spec, "listing_prefixes", ()) or ()
    return tuple(str(item) for item in raw if item)


def has_shopify_product_prefix(spec: object) -> bool:
    return any(
        item == "/products/" or item.startswith("/products/") for item in _listing_prefixes(spec)
    )


def looks_shopify_robots(body: str) -> bool:
    return SHOPIFY_ROBOTS_TOKEN in (body or "").lower()


def looks_shopify_origin(origin: str) -> bool:
    host = _hostname(origin)
    return host.startswith("shop.") and _is_public_hostname(host)


def looks_shopify_spec(spec: object) -> bool:
    path = getattr(spec, "catalog_feed_path", None)
    if isinstance(path, str) and "products.json" in path:
        return True
    for item in getattr(spec, "collection_paths", ()) or ():
        if str(item).startswith("/collections"):
            return True
    for item in getattr(spec, "query_paths", ()) or ():
        text = str(item)
        if "/collections/" in text and "products.json" in text:
            return True
    return has_shopify_product_prefix(spec)


def commerce_origins_for(spec: object) -> tuple[str, ...]:
    """Recorded origin, plus `shop.{apex}` when the spec looks Shopify-shaped."""
    recorded = origin_for_spec(spec)
    found: list[str] = []
    seen: set[str] = set()

    def add(origin: str) -> None:
        value = origin.rstrip("/")
        if not value or value in seen:
            return
        seen.add(value)
        found.append(value)

    if recorded:
        add(recorded)
    if not looks_shopify_spec(spec) and not has_shopify_product_prefix(spec):
        return tuple(found)
    host = _hostname(recorded) if recorded else str(getattr(spec, "domain", "") or "").lower()
    if not host or not _is_public_hostname(host) or host.startswith("shop."):
        return tuple(found)
    apex = host[4:] if host.startswith("www.") else host
    scheme = urlparse(recorded).scheme if recorded else "https"
    add(f"{scheme}://shop.{apex}")
    return tuple(found)


def strategy_origins_for(spec: object) -> tuple[str, ...]:
    """Origins that should receive Shopify feed / collection / sitemap URLs."""
    origins = commerce_origins_for(spec)
    if not origins:
        return ()
    shopify_hosts = [item for item in origins if looks_shopify_origin(item)]
    rest = [item for item in origins if item not in shopify_hosts]
    if shopify_hosts:
        return tuple(shopify_hosts + rest)
    if looks_shopify_spec(spec):
        return tuple(origins)
    return origins[:1]


def inferred_catalog_feed_path(spec: object) -> str | None:
    shopify_origin = any(looks_shopify_origin(item) for item in commerce_origins_for(spec))
    if looks_shopify_spec(spec) or shopify_origin:
        return SHOPIFY_FEED_PATH
    return None


def inferred_collection_template(spec: object) -> str | None:
    shopify_origin = any(looks_shopify_origin(item) for item in commerce_origins_for(spec))
    if looks_shopify_spec(spec) or shopify_origin:
        return SHOPIFY_COLLECTION_FEED
    return None


def inferred_sitemap_urls(spec: object) -> tuple[str, ...]:
    found: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        value = str(url or "").strip()
        if not value or value in seen:
            return
        seen.add(value)
        found.append(value)

    for raw in getattr(spec, "sitemap_urls", ()) or ():
        add(str(raw))
    for origin in strategy_origins_for(spec):
        add(f"{origin}{SHOPIFY_SITEMAP_PATH}")
    return tuple(found)


def host_variants(host: str) -> tuple[str, ...]:
    value = (host or "").lower().split(":")[0]
    if not value:
        return ()
    out = {value}
    if value.startswith("www."):
        apex = value[4:]
        out.add(apex)
        if _is_public_hostname(apex):
            out.add(f"shop.{apex}")
    elif value.startswith("shop."):
        apex = value[5:]
        out.add(apex)
        out.add(f"www.{apex}")
    elif _is_public_hostname(value):
        out.add(f"www.{value}")
        out.add(f"shop.{value}")
    return tuple(sorted(out))


def admitted_hosts_for(spec: object, manifest: object | None = None) -> tuple[str, ...]:
    hosts: set[str] = set()
    domain = getattr(manifest, "domain", None) if manifest is not None else None
    if isinstance(domain, str) and domain.strip():
        hosts.update(host_variants(domain.strip()))
    spec_domain = getattr(spec, "domain", None)
    if isinstance(spec_domain, str) and spec_domain.strip():
        hosts.update(host_variants(spec_domain.strip()))
    for origin in commerce_origins_for(spec):
        host = _hostname(origin)
        if host:
            hosts.update(host_variants(host))
    return tuple(sorted(hosts))


def maybe_decompress(body: bytes) -> bytes:
    """Decode a `.xml.gz` sitemap body. httpx already unwraps Content-Encoding."""
    if not body.startswith(b"\x1f\x8b"):
        return body
    try:
        return gzip.decompress(body)
    except OSError:
        return body


def is_sitemap_loc(url: str) -> bool:
    lowered = (url or "").lower()
    path = (urlparse(url).path or "").lower()
    if "sitemap" in lowered:
        return True
    return path.endswith(".xml.gz")


def requires_operator_credential(manifest: object) -> bool:
    """True when the adapter can only answer with an operator-provisioned secret.

    A published public token (Marginalia `public`) is not an operator secret.
    Self-hosted SearxNG is optional configuration, not a marketplace key.
    """
    auth = str(getattr(manifest, "authentication", "none") or "none").lower()
    if auth in {"none", ""}:
        return False
    access = str(getattr(manifest, "access_method", "") or "")
    if access == "self_hosted_api":
        return False
    limitations = " ".join(str(item) for item in (getattr(manifest, "known_limitations", ()) or ()))
    lowered = limitations.lower()
    if "public key" in lowered or "no signup" in lowered:
        return False
    return auth in {"oauth", "api_key", "cookie", "basic"}


def credential_gate_note(product: str) -> str:
    return (
        f"{product} is not part of uncredentialed reach. "
        "It can only answer with an operator-provisioned credential "
        "and is excluded from the live source plan."
    )


def robots_evidence(*, origin: str, body: str, status: str) -> dict[str, object]:
    """What was actually fetched for admission of this origin."""
    sitemaps: list[str] = []
    for raw in (body or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.lower().startswith("sitemap:"):
            loc = line.split(":", 1)[1].strip()
            if loc:
                sitemaps.append(loc)
    return {
        "origin": origin,
        "robots_url": f"{origin.rstrip('/')}/robots.txt",
        "robots_fetch_status": status,
        "robots_bytes": len(body or ""),
        "identifies_shopify": looks_shopify_robots(body),
        "sitemaps": sitemaps,
        "disallows_search": "disallow: /search" in (body or "").lower(),
    }


def feed_path_blocked_reason(url: str, disallowed: Sequence[str] = ()) -> str:
    path = (urlparse(url).path or "").lower()
    if path == "/search" or path.startswith("/search"):
        return "robots Disallow: /search"
    lowered_disallowed = [str(item) for item in disallowed if item]
    if any(item and item in url for item in lowered_disallowed):
        return "recorded disallowed path prefix"
    return "url is not admitted"
