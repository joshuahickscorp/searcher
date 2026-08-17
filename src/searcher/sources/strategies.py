"""Named reach strategies for an admitted shop.

A collection-handle guess is one strategy, not the only one. Site search,
the shop's own catalogue feed, and robots-allowed sitemaps are planned
alongside it. Coverage records each strategy and why it yielded nothing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from urllib.parse import quote_plus, urlparse

from searcher.sources.catalog import (
    catalog_feed_path_of,
    catalog_page_param_of,
    catalog_page_size_of,
    catalog_url_allowed,
    origin_for_spec,
)
from searcher.sources.platform import (
    inferred_collection_template,
    inferred_sitemap_urls,
    strategy_origins_for,
)
from searcher.sources.policy import policy_for
from searcher.sources.robots import path_matches_prefix

COLLECTION_SLUG = "collection_slug"
SITE_SEARCH = "site_search"
CATALOG_FEED = "catalog_feed"
SITEMAP = "sitemap"
OFFICIAL_API = "official_api"

STRATEGY_ORDER = (
    COLLECTION_SLUG,
    SITE_SEARCH,
    CATALOG_FEED,
    SITEMAP,
    OFFICIAL_API,
)

STATUS_QUEUED = "queued"
STATUS_SKIPPED = "skipped"
STATUS_BLOCKED = "blocked"
STATUS_TRIED = "tried"


@dataclass(frozen=True, slots=True)
class PlannedStrategy:
    name: str
    status: str
    reason: str
    urls: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "urls": list(self.urls),
            "yielded": 0,
        }


@dataclass(slots=True)
class StrategyAttempt:
    name: str
    status: str
    reason: str
    yielded: int = 0
    urls: list[str] = field(default_factory=list)

    def as_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "yielded": self.yielded,
            "urls": list(self.urls),
        }


def format_strategy_detail(attempts: Sequence[StrategyAttempt | Mapping[str, object]]) -> str:
    """One line per strategy: name, yield, and why it was empty or skipped."""
    parts: list[str] = []
    for item in attempts:
        if isinstance(item, StrategyAttempt):
            name = item.name
            status = item.status
            reason = item.reason
            yielded = item.yielded
        else:
            name = str(item.get("name") or "")
            status = str(item.get("status") or "")
            reason = str(item.get("reason") or "")
            raw_yielded = item.get("yielded")
            yielded = int(raw_yielded) if isinstance(raw_yielded, int) else 0
        if not name:
            continue
        if yielded > 0:
            parts.append(f"{name}: {yielded}")
        elif status in {STATUS_SKIPPED, STATUS_BLOCKED}:
            parts.append(f"{name}: {status} ({reason})")
        else:
            parts.append(f"{name}: 0 ({reason})")
    return "; ".join(parts)


def missing_key_note(
    *,
    key_names: Sequence[str],
    present: Mapping[str, str | None],
    signup_url: str,
    product: str,
) -> str:
    """Name the missing key and where to get it. Never a bare AUTH_REQUIRED."""
    missing = [name for name in key_names if not str(present.get(name) or "").strip()]
    if len(missing) == 1:
        listed = missing[0]
    elif len(missing) == 2:
        listed = f"{missing[0]} and {missing[1]}"
    elif missing:
        listed = ", ".join(missing[:-1]) + f", and {missing[-1]}"
    else:
        return (
            f"{product} credentials are set but the official API client is not implemented. "
            f"Docs: {signup_url}"
        )
    return f"missing {listed}. Create {product} credentials at {signup_url}"


def is_site_search_template(template: str) -> bool:
    lowered = template.lower()
    if "{slug}" in template and "/collection" in lowered:
        return False
    return any(
        token in lowered
        for token in ("/search", "?q=", "?s=", "/?s=", "{query}")
    )


def is_collection_template(template: str) -> bool:
    lowered = template.lower()
    return "{slug}" in template or "/collection" in lowered


def strategy_url_allowed(url: str, disallowed: Sequence[str] = ()) -> bool:
    return not path_matches_prefix(url, [item for item in disallowed if item])


def _search_admitted(spec: object) -> tuple[bool, str]:
    source_id = str(getattr(spec, "source_id", "") or "")
    recorded = policy_for(source_id) if source_id else None
    if recorded is not None and not recorded.search:
        return False, f"search is not an admitted use of {source_id or 'this source'}"
    capabilities = tuple(getattr(spec, "capabilities", ()) or ())
    if recorded is None and "text_search" not in capabilities:
        return False, f"search is not an admitted use of {source_id or 'this source'}"
    return True, ""


def _blocked_reason(url: str, disallowed: Sequence[str]) -> str:
    if path_matches_prefix(url, ["/search"]) or "/search" in (urlparse(url).path or "").lower():
        return "robots Disallow: /search"
    if path_matches_prefix(url, list(disallowed)):
        return "recorded disallowed path prefix"
    return "url is not admitted"


def _collection_urls(spec: object, query_text: str) -> list[str]:
    from searcher.sources.adapters.product import query_slugs, slugify_query

    origins = list(strategy_origins_for(spec))
    if not origins:
        recorded = origin_for_spec(spec)
        if recorded:
            origins = [recorded]
    if not origins:
        return []
    templates = [str(item) for item in (getattr(spec, "query_paths", ()) or ()) if item]
    inferred = inferred_collection_template(spec)
    if inferred and not any(is_collection_template(item) for item in templates):
        templates.append(inferred)
    slugs = query_slugs(query_text) or [slugify_query(query_text)]
    slugs = [slug for slug in slugs if slug]
    quoted = quote_plus(query_text)
    urls: list[str] = []
    seen: set[str] = set()
    for origin in origins:
        for template in templates:
            if not is_collection_template(template) or is_site_search_template(template):
                continue
            if "{slug}" in template:
                for slug in slugs:
                    url = f"{origin}{template.format(slug=slug, query=quoted)}"
                    if url not in seen:
                        seen.add(url)
                        urls.append(url)
            else:
                slug = slugs[0] if slugs else quoted
                url = f"{origin}{template.format(query=quoted, slug=slug)}"
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
    return urls


def _site_search_urls(spec: object, query_text: str) -> list[str]:
    origin = origin_for_spec(spec)
    if not origin:
        return []
    quoted = quote_plus(query_text)
    from searcher.sources.adapters.product import query_slugs, slugify_query

    slugs = query_slugs(query_text) or [slugify_query(query_text)]
    slug = next((item for item in slugs if item), quoted)
    urls: list[str] = []
    seen: set[str] = set()
    for template in getattr(spec, "query_paths", ()) or ():
        text = str(template)
        if not is_site_search_template(text):
            continue
        path = text.format(query=quoted, slug=slug)
        url = f"{origin}{path}"
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _sitemap_urls(spec: object) -> list[str]:
    return list(inferred_sitemap_urls(spec))


def plan_strategies(spec: object, query_text: str) -> list[PlannedStrategy]:
    """Decide every shop strategy. Does not fetch."""
    text = " ".join(str(query_text or "").split())
    disallowed = tuple(getattr(spec, "disallowed", ()) or ())
    source_id = str(getattr(spec, "source_id", "") or "")
    planned: list[PlannedStrategy] = []

    collection_urls = _collection_urls(spec, text) if text else []
    if not text:
        planned.append(
            PlannedStrategy(
                COLLECTION_SLUG,
                STATUS_SKIPPED,
                "no query text from which to derive a collection handle",
            )
        )
    elif not collection_urls:
        planned.append(
            PlannedStrategy(
                COLLECTION_SLUG,
                STATUS_SKIPPED,
                "no collection handle could be derived from the query",
            )
        )
    else:
        allowed = [url for url in collection_urls if strategy_url_allowed(url, disallowed)]
        blocked = [url for url in collection_urls if url not in allowed]
        if allowed:
            planned.append(
                PlannedStrategy(
                    COLLECTION_SLUG,
                    STATUS_QUEUED,
                    "guessed collection handle from the query",
                    tuple(allowed),
                )
            )
        else:
            planned.append(
                PlannedStrategy(
                    COLLECTION_SLUG,
                    STATUS_BLOCKED,
                    _blocked_reason(blocked[0], disallowed) if blocked else "url is not admitted",
                    tuple(blocked),
                )
            )

    search_ok, search_reason = _search_admitted(spec)
    search_urls = _site_search_urls(spec, text) if text else []
    if not search_ok:
        planned.append(PlannedStrategy(SITE_SEARCH, STATUS_SKIPPED, search_reason))
    elif not text:
        planned.append(PlannedStrategy(SITE_SEARCH, STATUS_SKIPPED, "no query text"))
    elif not search_urls:
        planned.append(
            PlannedStrategy(
                SITE_SEARCH,
                STATUS_SKIPPED,
                f"{source_id or 'source'} publishes no admitted site-search path",
            )
        )
    else:
        # Site search may use /search when policy admits it and the path is
        # not in the recorded disallowed list. catalog_url_allowed always
        # refuses /search (KIND) and is not the site-search gate.
        allowed = [url for url in search_urls if strategy_url_allowed(url, disallowed)]
        blocked = [url for url in search_urls if url not in allowed]
        if allowed:
            planned.append(
                PlannedStrategy(
                    SITE_SEARCH,
                    STATUS_QUEUED,
                    "admitted site search",
                    tuple(allowed),
                )
            )
        else:
            planned.append(
                PlannedStrategy(
                    SITE_SEARCH,
                    STATUS_BLOCKED,
                    _blocked_reason(blocked[0], disallowed) if blocked else "url is not admitted",
                    tuple(blocked),
                )
            )

    feed_path = catalog_feed_path_of(spec)
    origins = list(strategy_origins_for(spec))
    if not origins:
        recorded = origin_for_spec(spec)
        if recorded:
            origins = [recorded]
    if not feed_path:
        planned.append(
            PlannedStrategy(
                CATALOG_FEED,
                STATUS_SKIPPED,
                f"{source_id or 'source'} publishes no catalogue feed",
            )
        )
    elif not text:
        planned.append(
            PlannedStrategy(
                CATALOG_FEED,
                STATUS_SKIPPED,
                "no query text to match against the catalogue feed",
            )
        )
    else:
        from searcher.sources.catalog import build_catalog_page_url

        catalog_urls: list[str] = []
        blocked_urls: list[str] = []
        for origin in origins:
            first = build_catalog_page_url(
                origin,
                feed_path,
                page=1,
                page_param=catalog_page_param_of(spec),
                page_size=catalog_page_size_of(spec),
            )
            if catalog_url_allowed(first, disallowed):
                catalog_urls.append(first)
            else:
                blocked_urls.append(first)
        if catalog_urls:
            planned.append(
                PlannedStrategy(
                    CATALOG_FEED,
                    STATUS_QUEUED,
                    "shop-wide product feed, independent of collection handles",
                    tuple(catalog_urls),
                )
            )
        else:
            sample = blocked_urls[0] if blocked_urls else ""
            planned.append(
                PlannedStrategy(
                    CATALOG_FEED,
                    STATUS_BLOCKED,
                    _blocked_reason(sample, disallowed) if sample else "url is not admitted",
                    tuple(blocked_urls),
                )
            )

    sitemap_urls = _sitemap_urls(spec)
    if not sitemap_urls:
        planned.append(
            PlannedStrategy(
                SITEMAP,
                STATUS_SKIPPED,
                f"{source_id or 'source'} declares no sitemap",
            )
        )
    else:
        allowed = [url for url in sitemap_urls if strategy_url_allowed(url, disallowed)]
        blocked = [url for url in sitemap_urls if url not in allowed]
        if allowed:
            planned.append(
                PlannedStrategy(
                    SITEMAP,
                    STATUS_QUEUED,
                    "robots-allowed sitemap",
                    tuple(allowed),
                )
            )
        else:
            planned.append(
                PlannedStrategy(
                    SITEMAP,
                    STATUS_BLOCKED,
                    _blocked_reason(blocked[0], disallowed) if blocked else "url is not admitted",
                    tuple(blocked),
                )
            )
    return planned


def discover_seed_urls(planned: Sequence[PlannedStrategy]) -> list[str]:
    """Frontier seeds. Catalogue paging stays in the engine, not the frontier."""
    seeds: list[str] = []
    seen: set[str] = set()
    for item in planned:
        if item.status != STATUS_QUEUED:
            continue
        if item.name == CATALOG_FEED:
            continue
        for url in item.urls:
            if url in seen:
                continue
            seen.add(url)
            seeds.append(url)
    return seeds


def strategy_name_for_url(url: str) -> str:
    lowered = url.lower()
    path = (urlparse(url).path or "").lower()
    if "sitemap" in lowered:
        return SITEMAP
    if path == "/search" or path.startswith("/search") or "?q=" in lowered or "/?s=" in lowered:
        return SITE_SEARCH
    if path.endswith("/products.json") and "/collections/" not in path:
        return CATALOG_FEED
    if "/collections/" in path:
        return COLLECTION_SLUG
    return "page_fetch"


class StrategyBook:
    """Mutable per-source record of what was planned and what each strategy yielded."""

    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        self.attempts: dict[str, StrategyAttempt] = {}

    def load_plan(self, planned: Sequence[PlannedStrategy]) -> None:
        for item in planned:
            self.attempts[item.name] = StrategyAttempt(
                name=item.name,
                status=item.status,
                reason=item.reason,
                yielded=0,
                urls=list(item.urls),
            )

    def record(
        self,
        name: str,
        *,
        status: str,
        reason: str,
        yielded: int = 0,
        urls: Sequence[str] = (),
    ) -> None:
        existing = self.attempts.get(name)
        if existing is None:
            self.attempts[name] = StrategyAttempt(
                name=name,
                status=status,
                reason=reason,
                yielded=yielded,
                urls=list(urls),
            )
            return
        existing.status = status
        existing.reason = reason
        existing.yielded = yielded
        if urls:
            existing.urls = list(urls)

    def mark_tried(self, name: str, *, yielded: int, reason: str) -> None:
        existing = self.attempts.get(name)
        if existing is None:
            self.record(name, status=STATUS_TRIED, reason=reason, yielded=yielded)
            return
        if existing.status == STATUS_SKIPPED or existing.status == STATUS_BLOCKED:
            return
        existing.status = STATUS_TRIED
        existing.yielded = yielded
        existing.reason = reason

    def as_list(self) -> list[StrategyAttempt]:
        ordered = [self.attempts[name] for name in STRATEGY_ORDER if name in self.attempts]
        extras = [item for name, item in self.attempts.items() if name not in STRATEGY_ORDER]
        return ordered + extras

    def as_payload(self) -> list[dict[str, object]]:
        return [item.as_payload() for item in self.as_list()]

    def detail(self) -> str:
        return format_strategy_detail(self.as_list())
