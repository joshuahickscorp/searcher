"""Page a shop's public catalogue feed and shortlist products by feed text.

Slug-derived collection URLs miss an item when the brand does not map to a
collection handle. This path reads the shop's own products.json catalogue
(robots permitting), matches the campaign query against fields already in
the feed, and promotes only those members. Matching here is a shortlist:
it never records identity evidence.

A source that does not declare a catalogue feed is left alone.
"""

from __future__ import annotations

import os
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from searcher.sources.classify import origin_of, try_json
from searcher.sources.expand import IndexMember, shopify_members_from_body
from searcher.sources.robots import path_matches_prefix

CATALOG_FALLBACK_RECEIPT = "CatalogFallbackReceipt"

DEFAULT_PAGES_PER_SOURCE = 64
DEFAULT_PAGES_PER_CAMPAIGN = 80
DEFAULT_PROMOTE_PER_SOURCE = 24
DEFAULT_PROMOTE_PER_CAMPAIGN = 48
DEFAULT_PAGE_SIZE = 250
DEFAULT_PAGE_PARAM = "page"

# Always refused, even if a spec forgets to list it. KIND robots Disallow /search.
_SEARCH_PREFIXES = ("/search",)

_TOKEN_SPLIT = re.compile(r"[^\w]+", re.UNICODE)
_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "brand",
        "des",
        "for",
        "in",
        "item",
        "no",
        "of",
        "on",
        "or",
        "s",
        "ss",
        "such",
        "the",
        "to",
        "type",
        "with",
        "x",
        "yes",
    }
)
_GENERIC = frozenset(
    {
        "brand",
        "collection",
        "color",
        "colour",
        "date",
        "handle",
        "item",
        "men",
        "price",
        "product",
        "size",
        "tags",
        "type",
        "women",
    }
)
# Shortlist aids only. English query words that KIND stores in Japanese.
_SYNONYMS: dict[str, frozenset[str]] = {
    "pump": frozenset({"pump", "pumps", "パンプス", "ハイヒール"}),
    "pumps": frozenset({"pump", "pumps", "パンプス", "ハイヒール"}),
    "tee": frozenset({"tee", "tees", "tshirt", "tシャツ", "カットソー"}),
    "tshirt": frozenset({"tee", "tees", "tshirt", "tシャツ", "カットソー"}),
    "shirt": frozenset({"shirt", "shirts", "シャツ"}),
    "shirts": frozenset({"shirt", "shirts", "シャツ"}),
}


@dataclass(frozen=True, slots=True)
class CatalogCaps:
    pages_per_source: int
    pages_per_campaign: int
    promote_per_source: int
    promote_per_campaign: int


def catalog_caps_from_env() -> CatalogCaps:
    return CatalogCaps(
        pages_per_source=_env_cap("SEARCHER_CATALOG_PAGES_PER_SOURCE", DEFAULT_PAGES_PER_SOURCE),
        pages_per_campaign=_env_cap(
            "SEARCHER_CATALOG_PAGES_PER_CAMPAIGN", DEFAULT_PAGES_PER_CAMPAIGN
        ),
        promote_per_source=_env_cap(
            "SEARCHER_CATALOG_PROMOTE_PER_SOURCE", DEFAULT_PROMOTE_PER_SOURCE
        ),
        promote_per_campaign=_env_cap(
            "SEARCHER_CATALOG_PROMOTE_PER_CAMPAIGN", DEFAULT_PROMOTE_PER_CAMPAIGN
        ),
    )


def _env_cap(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


def catalog_feed_path_of(spec: object) -> str | None:
    """None when this source publishes no catalogue feed."""
    override = os.environ.get("SEARCHER_CATALOG_FEED_PATH")
    if override is not None and override.strip():
        return override.strip()
    path = getattr(spec, "catalog_feed_path", None)
    if isinstance(path, str) and path.strip():
        return path.strip()
    return None


def catalog_page_param_of(spec: object) -> str:
    raw = getattr(spec, "catalog_page_param", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return DEFAULT_PAGE_PARAM


def catalog_page_size_of(spec: object) -> int:
    raw = getattr(spec, "catalog_page_size", None)
    if isinstance(raw, int) and raw > 0:
        return raw
    return DEFAULT_PAGE_SIZE


def origin_for_spec(spec: object, fallback: str = "") -> str:
    explicit = getattr(spec, "origin", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().rstrip("/")
    domain = getattr(spec, "domain", None)
    if isinstance(domain, str) and domain.strip():
        return f"https://{domain.strip()}"
    return fallback


def catalog_url_allowed(url: str, disallowed: Sequence[str] = ()) -> bool:
    """Refuse robots-disallowed paths, including /search even if omitted from spec."""
    prefixes = [item for item in disallowed if item]
    for extra in _SEARCH_PREFIXES:
        if extra not in prefixes:
            prefixes.append(extra)
    if path_matches_prefix(url, prefixes):
        return False
    path = (urlparse(url).path or "/").lower()
    return not (path == "/search" or path.startswith("/search/"))


def build_catalog_page_url(
    origin: str,
    feed_path: str,
    *,
    page: int,
    page_param: str = DEFAULT_PAGE_PARAM,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> str:
    origin = origin.rstrip("/")
    path = feed_path if feed_path.startswith("/") else f"/{feed_path}"
    parsed = urlparse(origin + path)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["limit"] = str(max(1, page_size))
    query[page_param] = str(max(1, page))
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query), "")
    )


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    for src, dst in (("×", " "), ("✕", " "), ("/", " "), ("／", " ")):
        normalized = normalized.replace(src, dst)
    return normalized.casefold()


def query_terms(text: str) -> list[str]:
    """Significant tokens plus synonym expansions. Not an identity claim."""
    folded = _fold(text)
    out: list[str] = []
    seen: set[str] = set()
    for raw in _TOKEN_SPLIT.split(folded):
        token = raw.strip()
        if len(token) < 2 or token in _STOP:
            continue
        variants = _SYNONYMS.get(token, frozenset({token}))
        for item in variants:
            if item not in seen:
                seen.add(item)
                out.append(item)
    return out


def haystack_from_fields(
    *,
    title: str | None = None,
    brand: str | None = None,
    handle: str | None = None,
    price: str | None = None,
    images: Sequence[str] = (),
    description: str | None = None,
    extra: Sequence[str] = (),
) -> str:
    parts: list[str] = []
    for value in (title, brand, handle, price, description, *extra, *images):
        if value:
            parts.append(str(value))
    return _fold(" ".join(parts))


def haystack_from_product(product: dict[str, Any], member: IndexMember | None = None) -> str:
    tags = product.get("tags")
    tag_text = ""
    if isinstance(tags, str):
        tag_text = tags
    elif isinstance(tags, list):
        tag_text = " ".join(str(item) for item in tags if item)
    extra = [
        str(product.get("product_type") or ""),
        tag_text,
        str(product.get("vendor") or ""),
    ]
    images = list(member.images) if member is not None else []
    if not images:
        for image in product.get("images") or []:
            if isinstance(image, dict) and image.get("src"):
                images.append(str(image["src"]))
            elif isinstance(image, str) and image:
                images.append(image)
    variants = product.get("variants") or []
    price = None
    if variants and isinstance(variants[0], dict):
        raw_price = variants[0].get("price")
        if raw_price is not None:
            price = str(raw_price)
    return haystack_from_fields(
        title=str(product.get("title") or "") or (member.title if member else None),
        brand=str(product.get("vendor") or "") or (member.brand if member else None),
        handle=str(product.get("handle") or "") or (member.handle if member else None),
        price=price or (member.price if member else None),
        images=images,
        description=(member.description if member else None),
        extra=extra,
    )


def _haystack_tokens(haystack: str) -> set[str]:
    return {part for part in _TOKEN_SPLIT.split(haystack) if len(part) >= 2}


def _term_hits(term: str, haystack: str, tokens: set[str]) -> bool:
    if any(ord(char) > 127 for char in term):
        return term in haystack
    return term in tokens


def _distinctive(terms: Sequence[str]) -> list[str]:
    out: list[str] = []
    for term in terms:
        if term in _GENERIC:
            continue
        if any(ord(char) > 127 for char in term):
            out.append(term)
            continue
        if len(term) >= 4:
            out.append(term)
    return out


def match_score(query_texts: Sequence[str], haystack: str) -> int:
    """How many distinctive query terms hit the feed text. Zero means do not promote."""
    if not haystack:
        return 0
    tokens = _haystack_tokens(haystack)
    best = 0
    for text in query_texts:
        terms = query_terms(text)
        if not terms:
            continue
        needed = _distinctive(terms)
        if not needed:
            continue
        hits = sum(1 for term in needed if _term_hits(term, haystack, tokens))
        if hits > best:
            best = hits
    return best


def feed_text_matches(query_texts: Sequence[str], haystack: str) -> bool:
    return match_score(query_texts, haystack) > 0


@dataclass(slots=True)
class CatalogResult:
    source_id: str
    catalog_url: str
    pages_read: int
    products_seen: int
    products_matched: int
    products_promoted: int
    dropped: int
    drop_reasons: dict[str, int]
    pages_per_source_cap: int
    pages_per_campaign_cap: int
    promote_per_source_cap: int
    promote_per_campaign_cap: int
    campaign_pages_before: int
    campaign_pages_after: int
    campaign_promoted_before: int
    campaign_promoted_after: int
    stopped_reason: str
    promoted: list[IndexMember] = field(default_factory=list)
    member_urls: list[str] = field(default_factory=list)
    requested_urls: list[str] = field(default_factory=list)

    def as_payload(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "catalog_url": self.catalog_url,
            "pages_read": self.pages_read,
            "products_seen": self.products_seen,
            "products_matched": self.products_matched,
            "products_promoted": self.products_promoted,
            "dropped": self.dropped,
            "drop_reasons": dict(self.drop_reasons),
            "pages_per_source_cap": self.pages_per_source_cap,
            "pages_per_campaign_cap": self.pages_per_campaign_cap,
            "promote_per_source_cap": self.promote_per_source_cap,
            "promote_per_campaign_cap": self.promote_per_campaign_cap,
            "campaign_pages_before": self.campaign_pages_before,
            "campaign_pages_after": self.campaign_pages_after,
            "campaign_promoted_before": self.campaign_promoted_before,
            "campaign_promoted_after": self.campaign_promoted_after,
            "stopped_reason": self.stopped_reason,
            "member_urls": list(self.member_urls),
        }


def _empty_result(
    *,
    source_id: str,
    catalog_url: str,
    caps: CatalogCaps,
    campaign_pages_already: int,
    campaign_promoted_already: int,
    reason: str,
    drop_reasons: dict[str, int] | None = None,
) -> CatalogResult:
    reasons = dict(drop_reasons or {})
    return CatalogResult(
        source_id=source_id,
        catalog_url=catalog_url,
        pages_read=0,
        products_seen=0,
        products_matched=0,
        products_promoted=0,
        dropped=sum(reasons.values()),
        drop_reasons=reasons,
        pages_per_source_cap=caps.pages_per_source,
        pages_per_campaign_cap=caps.pages_per_campaign,
        promote_per_source_cap=caps.promote_per_source,
        promote_per_campaign_cap=caps.promote_per_campaign,
        campaign_pages_before=campaign_pages_already,
        campaign_pages_after=campaign_pages_already,
        campaign_promoted_before=campaign_promoted_already,
        campaign_promoted_after=campaign_promoted_already,
        stopped_reason=reason,
    )


def page_catalog(
    *,
    origin: str,
    feed_path: str,
    query_texts: Sequence[str],
    fetch_page: Callable[[str], bytes],
    disallowed: Sequence[str] = (),
    page_param: str = DEFAULT_PAGE_PARAM,
    page_size: int = DEFAULT_PAGE_SIZE,
    caps: CatalogCaps | None = None,
    campaign_pages_already: int = 0,
    campaign_promoted_already: int = 0,
    seen_urls: set[str] | None = None,
    allowed_hosts: Sequence[str] = (),
    source_id: str = "",
) -> CatalogResult:
    """Read catalogue pages, match in the feed, promote only hits.

    ``fetch_page`` is called only for URLs that pass ``catalog_url_allowed``.
    """
    resolved = caps or catalog_caps_from_env()
    first_url = build_catalog_page_url(
        origin, feed_path, page=1, page_param=page_param, page_size=page_size
    )
    if not feed_path:
        return _empty_result(
            source_id=source_id,
            catalog_url=first_url,
            caps=resolved,
            campaign_pages_already=campaign_pages_already,
            campaign_promoted_already=campaign_promoted_already,
            reason="no_catalog_feed",
        )
    usable_queries = [text for text in query_texts if str(text or "").strip()]
    if not usable_queries:
        return _empty_result(
            source_id=source_id,
            catalog_url=first_url,
            caps=resolved,
            campaign_pages_already=campaign_pages_already,
            campaign_promoted_already=campaign_promoted_already,
            reason="no_query",
        )
    if resolved.pages_per_source <= 0 or resolved.pages_per_campaign <= 0:
        return _empty_result(
            source_id=source_id,
            catalog_url=first_url,
            caps=resolved,
            campaign_pages_already=campaign_pages_already,
            campaign_promoted_already=campaign_promoted_already,
            reason="page_cap",
        )

    seen = set(seen_urls or ())
    allowed = {host.lower() for host in allowed_hosts if host}
    reasons: Counter[str] = Counter()
    scored: list[tuple[int, IndexMember]] = []
    requested: list[str] = []
    pages_read = 0
    products_seen = 0
    stopped = "exhausted"
    source_page_budget = resolved.pages_per_source
    campaign_page_budget = max(0, resolved.pages_per_campaign - campaign_pages_already)

    page = 1
    while pages_read < source_page_budget and pages_read < campaign_page_budget:
        url = build_catalog_page_url(
            origin, feed_path, page=page, page_param=page_param, page_size=page_size
        )
        if not catalog_url_allowed(url, disallowed):
            reasons["robots_disallowed"] += 1
            stopped = "robots_disallowed"
            break
        requested.append(url)
        body = fetch_page(url)
        pages_read += 1
        members = shopify_members_from_body(body, url, origin=origin or origin_of(url))
        payload = try_json(body)
        raw_products: list[dict[str, Any]] = []
        if isinstance(payload, dict) and isinstance(payload.get("products"), list):
            raw_products = [item for item in payload["products"] if isinstance(item, dict)]
        if not members and not raw_products:
            stopped = "exhausted"
            break
        count = max(len(members), len(raw_products))
        products_seen += count
        for index in range(count):
            member = members[index] if index < len(members) else None
            raw = raw_products[index] if index < len(raw_products) else {}
            if member is None:
                reasons["missing_url"] += 1
                continue
            if not member.url:
                reasons["missing_url"] += 1
                continue
            host = (urlparse(member.url).hostname or "").lower()
            if allowed and host not in allowed:
                reasons["host_not_admitted"] += 1
                continue
            if member.url.rstrip("/") in seen or member.url in seen:
                reasons["already_seen"] += 1
                continue
            haystack = haystack_from_product(raw, member)
            score = match_score(usable_queries, haystack)
            if score <= 0:
                reasons["feed_text_no_match"] += 1
                continue
            scored.append((score, member))
            seen.add(member.url)
        if count < page_size:
            stopped = "exhausted"
            break
        page += 1
    else:
        if pages_read >= source_page_budget:
            stopped = "per_source_page_cap"
        elif pages_read >= campaign_page_budget:
            stopped = "per_campaign_page_cap"

    scored.sort(key=lambda item: (-item[0], item[1].url))
    promoted: list[IndexMember] = []
    source_promote = resolved.promote_per_source
    campaign_promote = max(0, resolved.promote_per_campaign - campaign_promoted_already)
    for _score, member in scored:
        if len(promoted) >= source_promote:
            reasons["per_source_promote_cap"] += 1
            continue
        if len(promoted) >= campaign_promote:
            reasons["per_campaign_promote_cap"] += 1
            continue
        promoted.append(member)
    dropped = sum(reasons.values())
    return CatalogResult(
        source_id=source_id,
        catalog_url=first_url,
        pages_read=pages_read,
        products_seen=products_seen,
        products_matched=len(scored),
        products_promoted=len(promoted),
        dropped=dropped,
        drop_reasons=dict(reasons),
        pages_per_source_cap=resolved.pages_per_source,
        pages_per_campaign_cap=resolved.pages_per_campaign,
        promote_per_source_cap=resolved.promote_per_source,
        promote_per_campaign_cap=resolved.promote_per_campaign,
        campaign_pages_before=campaign_pages_already,
        campaign_pages_after=campaign_pages_already + pages_read,
        campaign_promoted_before=campaign_promoted_already,
        campaign_promoted_after=campaign_promoted_already + len(promoted),
        stopped_reason=stopped,
        promoted=promoted,
        member_urls=[member.url for member in promoted],
        requested_urls=requested,
    )
