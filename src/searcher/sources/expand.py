"""Expand an index document into member product URLs.

Members re-enter the frontier as ordinary work. Caps are enforced and every
drop is recorded. Fields taken from a structured feed are not invented.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

from searcher.contracts.enums import DocumentClass, ExtractionMethod, FactClass, FactOrigin
from searcher.contracts.models import ListingCandidate, ListingImage, RawListing
from searcher.contracts.primitives import ClassifiedFact
from searcher.core.ids import new_id, sha256_hex
from searcher.core.time import utc_now
from searcher.sources.classify import (
    classify_acquired_document,
    host_of,
    looks_like_index_url,
    origin_of,
    try_json,
)

DEFAULT_PER_INDEX_CAP = 24
DEFAULT_PER_CAMPAIGN_CAP = 48
INDEX_EXPANSION_RECEIPT = "IndexExpansionReceipt"
IMAGES_MISSING_KEY = "images_missing_reason"

_FEED_NO_IMAGES = "feed_listed_no_images"
_PAGE_NO_IMAGES = "page_extracted_no_images"
_PRODUCT_PATH_HINTS = (
    "/products/",
    "/product/",
    "/listing/",
    "/listings/",
    "/items/",
    "/itm/",
    "/c/goods/",
)
_JSON_LD_SCRIPT = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
_SITEMAP_LOC = re.compile(r"<loc>\s*([^<]+)\s*</loc>", re.I)


@dataclass(frozen=True, slots=True)
class ExpansionCaps:
    per_index: int
    per_campaign: int


def expansion_caps_from_env() -> ExpansionCaps:
    return ExpansionCaps(
        per_index=_env_cap("SEARCHER_INDEX_EXPAND_PER_INDEX", DEFAULT_PER_INDEX_CAP),
        per_campaign=_env_cap("SEARCHER_INDEX_EXPAND_PER_CAMPAIGN", DEFAULT_PER_CAMPAIGN_CAP),
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


@dataclass(slots=True)
class IndexMember:
    url: str
    title: str | None = None
    price: str | None = None
    currency: str | None = None
    images: list[str] = field(default_factory=list)
    handle: str | None = None
    description: str | None = None
    brand: str | None = None
    availability: str | None = None
    from_feed: bool = False
    extraction_method: str = ExtractionMethod.UNKNOWN.value

    def image_absence_reason(self) -> str | None:
        if self.images:
            return None
        if self.from_feed:
            return _FEED_NO_IMAGES
        return _PAGE_NO_IMAGES


@dataclass(slots=True)
class ExpansionResult:
    document_class: DocumentClass
    index_url: str
    members_found: int
    taken: list[IndexMember]
    dropped: int
    drop_reasons: dict[str, int]
    per_index_cap: int
    per_campaign_cap: int
    campaign_taken_before: int
    campaign_taken_after: int

    def as_payload(self) -> dict[str, object]:
        return {
            "index_url": self.index_url,
            "document_class": self.document_class.value,
            "members_found": self.members_found,
            "taken": len(self.taken),
            "dropped": self.dropped,
            "drop_reasons": dict(self.drop_reasons),
            "per_index_cap": self.per_index_cap,
            "per_campaign_cap": self.per_campaign_cap,
            "campaign_taken_before": self.campaign_taken_before,
            "campaign_taken_after": self.campaign_taken_after,
            "member_urls": [member.url for member in self.taken],
        }


def _canon(url: str) -> str:
    try:
        from searcher.normalization.url import canonicalize_url

        return canonicalize_url(url)
    except Exception:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{parsed.scheme}://{(parsed.hostname or '').lower()}{path}{query}"


def _host_allowed(url: str, allowed_hosts: Sequence[str]) -> bool:
    host = host_of(url)
    if not host:
        return False
    allowed = {item.lower() for item in allowed_hosts if item}
    if not allowed:
        return False
    return host in allowed


def shopify_members_from_body(body: bytes, url: str, *, origin: str) -> list[IndexMember]:
    """Every product object in a Shopify products.json / product.json body."""
    payload = try_json(body)
    if not isinstance(payload, dict):
        return []
    products: list[dict[str, Any]] = []
    if isinstance(payload.get("products"), list):
        products = [item for item in payload["products"] if isinstance(item, dict)]
    elif isinstance(payload.get("product"), dict):
        products = [payload["product"]]
    else:
        return []
    base = origin.rstrip("/") or origin_of(url)
    members: list[IndexMember] = []
    for product in products:
        handle = str(product.get("handle") or product.get("id") or "").strip()
        if not handle:
            continue
        product_url = f"{base}/products/{handle}"
        images = _shopify_images(product)
        variants = product.get("variants") or []
        variant = variants[0] if variants and isinstance(variants[0], dict) else {}
        price = variant.get("price") if isinstance(variant, dict) else None
        currency = _shopify_currency(product, variant if isinstance(variant, dict) else {})
        available = None
        if isinstance(variant, dict) and "available" in variant:
            available = "InStock" if variant.get("available") else "SoldOut"
        elif product.get("published_at"):
            available = "InStock"
        raw_description = product.get("body_html")
        description = (
            _strip_tags(raw_description) or None if isinstance(raw_description, str) else None
        )
        title = product.get("title")
        members.append(
            IndexMember(
                url=product_url,
                title=str(title) if title not in (None, "") else None,
                price=str(price) if price is not None and price != "" else None,
                currency=currency,
                images=images,
                handle=handle,
                description=description,
                brand=str(product["vendor"]) if product.get("vendor") else None,
                availability=available,
                from_feed=True,
                extraction_method=ExtractionMethod.API.value,
            )
        )
    return members


def _shopify_images(product: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for image in product.get("images") or []:
        src = _image_src(image)
        if src and src not in found:
            found.append(src)
    featured = product.get("image") or product.get("featured_image")
    src = _image_src(featured)
    if src and src not in found:
        found.insert(0, src)
    return found


def _image_src(image: object) -> str | None:
    if isinstance(image, str) and image:
        return image
    if isinstance(image, dict):
        src = image.get("src") or image.get("url") or image.get("contentUrl")
        if src:
            return str(src)
    return None


def _shopify_currency(product: dict[str, Any], variant: dict[str, Any]) -> str | None:
    for blob in (variant, product):
        for key in ("currency", "price_currency", "presentment_currency"):
            value = blob.get(key)
            if isinstance(value, str) and value:
                return value
        presentment = blob.get("presentment_prices")
        if isinstance(presentment, list) and presentment and isinstance(presentment[0], dict):
            price = presentment[0].get("price")
            if isinstance(price, dict):
                currency = price.get("currency_code") or price.get("currency")
                if isinstance(currency, str) and currency:
                    return currency
    return None


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).replace("&nbsp;", " ").strip()


def _json_ld_item_list(body: bytes, url: str) -> list[IndexMember]:
    text = body.decode("utf-8-sig", errors="replace")
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
    members: list[IndexMember] = []
    seen: set[str] = set()
    for block in blocks:
        types = block.get("@type")
        names = types if isinstance(types, list) else [types]
        lowered = [str(name).lower() for name in names if name]
        if not any("itemlist" in name or "offercatalog" in name for name in lowered):
            continue
        elements = block.get("itemListElement") or block.get("itemList") or []
        if not isinstance(elements, list):
            continue
        for element in elements:
            href = _ld_item_url(element, url)
            if not href or href in seen:
                continue
            seen.add(href)
            title = None
            if isinstance(element, dict):
                item = element.get("item")
                if isinstance(item, dict):
                    title = item.get("name") or item.get("title")
                title = title or element.get("name")
            members.append(
                IndexMember(
                    url=href,
                    title=str(title) if title else None,
                    from_feed=False,
                    extraction_method=ExtractionMethod.JSON_LD.value,
                )
            )
    return members


def _ld_item_url(element: object, base: str) -> str | None:
    if isinstance(element, str) and element:
        return urljoin(base, element)
    if not isinstance(element, dict):
        return None
    item = element.get("item")
    if isinstance(item, str) and item:
        return urljoin(base, item)
    if isinstance(item, dict):
        href = item.get("url") or item.get("@id")
        if href:
            return urljoin(base, str(href))
    href = element.get("url") or element.get("@id")
    if href:
        return urljoin(base, str(href))
    return None


def _sitemap_query_tokens(query_texts: Sequence[str]) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for text in query_texts:
        for part in str(text).split():
            token = part.lower()
            if len(token) > 2 and token not in seen:
                seen.add(token)
                tokens.append(token)
    return tokens


def _sitemap_loc_matches_query(url: str, tokens: Sequence[str]) -> bool:
    if not tokens:
        return True
    lowered = url.lower()
    return any(token.replace(" ", "-") in lowered or token in lowered for token in tokens)


def _sitemap_members(body: bytes, listing_prefixes: Sequence[str]) -> list[IndexMember]:
    text = body.decode("utf-8-sig", errors="replace")
    locs = [match.group(1).strip() for match in _SITEMAP_LOC.finditer(text)]
    members: list[IndexMember] = []
    for loc in locs:
        if listing_prefixes and not any(prefix in loc for prefix in listing_prefixes):
            continue
        if looks_like_index_url(loc):
            continue
        members.append(
            IndexMember(
                url=loc,
                from_feed=False,
                extraction_method=ExtractionMethod.SITEMAP.value,
            )
        )
    return members


def _html_members(
    body: bytes,
    url: str,
    listing_prefixes: Sequence[str],
    allowed_hosts: Sequence[str],
) -> list[IndexMember]:
    try:
        from searcher.sources.adapters.generic_page import listing_links
    except Exception:
        return []
    prefixes = list(listing_prefixes) or list(_PRODUCT_PATH_HINTS)
    html = body.decode("utf-8-sig", errors="replace")
    members: list[IndexMember] = []
    seen: set[str] = set()
    try:
        hrefs = listing_links(html, url, prefixes)
    except Exception:
        return []
    for href in hrefs:
        if looks_like_index_url(href):
            continue
        if not _host_allowed(href, allowed_hosts):
            continue
        canon = _canon(href)
        if canon in seen:
            continue
        seen.add(canon)
        members.append(
            IndexMember(
                url=href,
                from_feed=False,
                extraction_method=ExtractionMethod.DOM.value,
            )
        )
    return members


def extract_index_members(
    *,
    url: str,
    body: bytes,
    listing_prefixes: Sequence[str] = (),
    allowed_hosts: Sequence[str] = (),
) -> list[IndexMember]:
    """JSON feed, then JSON-LD, then sitemap, then HTML links."""
    origin = origin_of(url)
    shopify = shopify_members_from_body(body, url, origin=origin)
    if shopify:
        return shopify
    ld = _json_ld_item_list(body, url)
    if ld:
        return ld
    sitemap = _sitemap_members(body, listing_prefixes)
    if sitemap:
        return sitemap
    return _html_members(body, url, listing_prefixes, allowed_hosts)


def expand_index(
    *,
    url: str,
    body: bytes,
    listing_prefixes: Sequence[str] = (),
    allowed_hosts: Sequence[str] = (),
    seen_urls: set[str] | None = None,
    per_index_cap: int | None = None,
    per_campaign_cap: int | None = None,
    campaign_taken: int = 0,
    child_depth: int = 1,
    max_depth: int = 3,
    query_texts: Sequence[str] = (),
) -> ExpansionResult:
    caps = expansion_caps_from_env()
    index_cap = caps.per_index if per_index_cap is None else max(0, per_index_cap)
    campaign_cap = caps.per_campaign if per_campaign_cap is None else max(0, per_campaign_cap)
    members = extract_index_members(
        url=url,
        body=body,
        listing_prefixes=listing_prefixes,
        allowed_hosts=allowed_hosts,
    )
    if query_texts:
        # Order by how well the feed's own text matches the campaign query before
        # the cap applies. Taking the first N in feed order meant a 250-product
        # collection was sampled by position: the item being searched for sat at
        # position 104 and the cap was 24, so it was never reached. Sorting is
        # stable, so an unscored feed keeps its original order.
        from searcher.sources.catalog import haystack_from_product, match_score

        members = sorted(
            members,
            key=lambda m: -match_score(query_texts, haystack_from_product({}, m)),
        )
    seen = set(seen_urls or ())
    index_canon = _canon(url)
    seen.add(index_canon)
    reasons: Counter[str] = Counter()
    taken: list[IndexMember] = []
    sitemap_tokens: list[str] = []
    if query_texts and "sitemap" in url.lower():
        sitemap_tokens = _sitemap_query_tokens(query_texts)
    if child_depth > max_depth:
        reasons["max_depth"] += len(members)
        return ExpansionResult(
            document_class=DocumentClass.INDEX,
            index_url=url,
            members_found=len(members),
            taken=[],
            dropped=len(members),
            drop_reasons=dict(reasons),
            per_index_cap=index_cap,
            per_campaign_cap=campaign_cap,
            campaign_taken_before=campaign_taken,
            campaign_taken_after=campaign_taken,
        )
    for member in members:
        if not member.url:
            reasons["missing_url"] += 1
            continue
        if sitemap_tokens and not _sitemap_loc_matches_query(member.url, sitemap_tokens):
            reasons["query_not_in_loc"] += 1
            continue
        if not _host_allowed(member.url, allowed_hosts):
            reasons["host_not_admitted"] += 1
            continue
        canon = _canon(member.url)
        if canon == index_canon:
            reasons["duplicate_of_index"] += 1
            continue
        if canon in seen:
            reasons["already_seen"] += 1
            continue
        if len(taken) >= index_cap:
            reasons["per_index_cap"] += 1
            continue
        if campaign_taken + len(taken) >= campaign_cap:
            reasons["per_campaign_cap"] += 1
            continue
        taken.append(member)
        seen.add(canon)
    dropped = sum(reasons.values())
    return ExpansionResult(
        document_class=DocumentClass.INDEX,
        index_url=url,
        members_found=len(members),
        taken=taken,
        dropped=dropped,
        drop_reasons=dict(reasons),
        per_index_cap=index_cap,
        per_campaign_cap=campaign_cap,
        campaign_taken_before=campaign_taken,
        campaign_taken_after=campaign_taken + len(taken),
    )


def raw_listing_from_member(
    member: IndexMember,
    *,
    source_adapter: str,
    content_digest: str | None = None,
    language: str | None = None,
) -> RawListing:
    images = [{"url": src} for src in member.images]
    reason = member.image_absence_reason()
    digest = content_digest or sha256_hex(member.url.encode("utf-8"))
    payload: dict[str, object] = {
        "title": member.title,
        "description": member.description,
        "brand": member.brand,
        "model": member.handle,
        "price_original": member.price,
        "currency": member.currency,
        "availability": member.availability,
        "images": images,
        "listing_id": member.handle,
        "canonical_url": member.url,
        "page_type": "product",
        "extraction_method": member.extraction_method,
        "from_index_feed": member.from_feed,
    }
    if language:
        payload["language"] = language
        payload["source_region"] = language
    if reason:
        payload[IMAGES_MISSING_KEY] = reason
    return RawListing(
        source_adapter=source_adapter,
        url=member.url,
        payload=payload,
        content_digest=digest,
        fetched_at=utc_now(),
    )


def member_frontier_payload(
    member: IndexMember, *, index_url: str, work_key: str
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "from": work_key,
        "from_index": index_url,
        "from_index_feed": member.from_feed,
        "canonical_url": member.url,
        "title": member.title,
        "description": member.description,
        "brand": member.brand,
        "model": member.handle,
        "price_original": member.price,
        "currency": member.currency,
        "availability": member.availability,
        "images": [{"url": src} for src in member.images],
        "listing_id": member.handle,
        "extraction_method": member.extraction_method,
        "page_type": "product",
    }
    reason = member.image_absence_reason()
    if reason:
        payload[IMAGES_MISSING_KEY] = reason
    return payload


def member_from_frontier_payload(payload: dict[str, Any], url: str) -> IndexMember:
    images_raw = payload.get("images") or []
    images: list[str] = []
    if isinstance(images_raw, list):
        for item in images_raw:
            if isinstance(item, dict) and item.get("url"):
                images.append(str(item["url"]))
            elif isinstance(item, str) and item:
                images.append(item)
    handle = payload.get("listing_id") or payload.get("model")
    return IndexMember(
        url=str(payload.get("canonical_url") or url),
        title=str(payload["title"]) if payload.get("title") else None,
        price=str(payload["price_original"]) if payload.get("price_original") else None,
        currency=str(payload["currency"]) if payload.get("currency") else None,
        images=images,
        handle=str(handle) if handle else None,
        description=str(payload["description"]) if payload.get("description") else None,
        brand=str(payload["brand"]) if payload.get("brand") else None,
        availability=str(payload["availability"]) if payload.get("availability") else None,
        from_feed=bool(payload.get("from_index_feed")),
        extraction_method=str(payload.get("extraction_method") or ExtractionMethod.API.value),
    )


def attach_image_absence(
    candidate: ListingCandidate,
    raw: RawListing | None = None,
    *,
    reason: str | None = None,
) -> ListingCandidate:
    if candidate.images:
        return candidate
    recorded = reason
    if recorded is None and raw is not None:
        value = raw.payload.get(IMAGES_MISSING_KEY)
        if isinstance(value, str) and value:
            recorded = value
    if recorded is None:
        recorded = _PAGE_NO_IMAGES
    data = dict(candidate.structured_data)
    data[IMAGES_MISSING_KEY] = recorded
    return candidate.model_copy(update={"structured_data": data})


def _minimal_candidate(raw: RawListing) -> ListingCandidate:
    now = raw.fetched_at
    candidate_id = new_id()
    images: list[ListingImage] = []
    images_raw = raw.payload.get("images")
    if not isinstance(images_raw, list):
        images_raw = []
    for image in images_raw:
        if not isinstance(image, dict):
            continue
        remote = str(image.get("url") or "")
        if not remote:
            continue
        images.append(
            ListingImage(
                listing_image_id=new_id(),
                candidate_id=candidate_id,
                remote_url=remote,
            )
        )
    title = raw.payload.get("title")
    return ListingCandidate(
        candidate_id=candidate_id,
        canonical_url=str(raw.payload.get("canonical_url") or raw.url),
        source_adapter=raw.source_adapter,
        source_listing_id=str(raw.payload.get("listing_id") or "") or None,
        title=(
            ClassifiedFact(
                value=str(title),
                fact_class=FactClass.REPORTED_BY_SELLER,
                origin=FactOrigin.SELLER,
            )
            if title
            else None
        ),
        images=images,
        structured_data={"raw": dict(raw.payload)},
        first_seen_at=now,
        last_checked_at=now,
        source_evidence=[raw.content_digest],
    )


def candidate_from_member(
    member: IndexMember,
    *,
    source_adapter: str,
    language: str | None = None,
) -> ListingCandidate:
    raw = raw_listing_from_member(member, source_adapter=source_adapter, language=language)
    try:
        from searcher.normalization.listing import normalize_raw

        candidate = normalize_raw(raw)
    except Exception:
        candidate = _minimal_candidate(raw)
    return attach_image_absence(candidate, raw)


def expand_index_to_candidates(
    url: str,
    body: bytes,
    *,
    source_adapter: str,
    listing_prefixes: Sequence[str] = ("/products/",),
    allowed_hosts: Sequence[str] | None = None,
    per_index_cap: int | None = None,
    per_campaign_cap: int | None = None,
    seen_urls: set[str] | None = None,
    language: str | None = None,
) -> tuple[list[ListingCandidate], ExpansionResult]:
    """Classify, expand, and materialize. The index URL is never a candidate."""
    classification = classify_acquired_document(
        url=url, body=body, listing_prefixes=listing_prefixes
    )
    hosts = list(allowed_hosts or [])
    if not hosts:
        host = host_of(url)
        if host:
            hosts.append(host)
    if classification is not DocumentClass.INDEX and not looks_like_index_url(url):
        empty = ExpansionResult(
            document_class=classification,
            index_url=url,
            members_found=0,
            taken=[],
            dropped=0,
            drop_reasons={},
            per_index_cap=per_index_cap or expansion_caps_from_env().per_index,
            per_campaign_cap=per_campaign_cap or expansion_caps_from_env().per_campaign,
            campaign_taken_before=0,
            campaign_taken_after=0,
        )
        return [], empty
    result = expand_index(
        url=url,
        body=body,
        listing_prefixes=listing_prefixes,
        allowed_hosts=hosts,
        seen_urls=seen_urls,
        per_index_cap=per_index_cap,
        per_campaign_cap=per_campaign_cap,
    )
    candidates = [
        candidate_from_member(member, source_adapter=source_adapter, language=language)
        for member in result.taken
    ]
    index_canon = _canon(url)
    candidates = [item for item in candidates if _canon(item.canonical_url) != index_canon]
    return candidates, result
