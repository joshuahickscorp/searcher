"""An admitted shop is searched by its feed, not only by a guessed collection."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest
from tests.conftest import make_budget, make_intent

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import QueryType, SourceAdmission, SourceOutcome
from searcher.contracts.models import QueryVariant
from searcher.core.ids import new_id
from searcher.sources.adapters import ADAPTER_REGISTRY
from searcher.sources.adapters.product import ProductPageAdapter, SourceSpec
from searcher.sources.engine import DiscoveryEngine
from searcher.sources.live_runner import LiveDiscoveryRunner
from searcher.sources.strategies import CATALOG_FEED, COLLECTION_SLUG, SITE_SEARCH

ROBOTS = b"User-agent: *\nDisallow: /search\nAllow: /\nCrawl-delay: 0\nSitemap: /sitemap.xml\n"

PERSONSOUL = {
    "id": 1,
    "handle": "8072000111361",
    "title": "カーブブレード刺繍デニムパンツ",
    "vendor": "personsoul",
    "product_type": "パンツ",
    "tags": "Men",
    "body_html": "<p>personsoul denim</p>",
    "variants": [{"price": "18000", "available": True}],
    "images": [{"src": "https://cdn.example.test/personsoul.jpg"}],
}
OTHER = {
    "id": 2,
    "handle": "8006002304964",
    "title": "パンツ",
    "vendor": "DIESEL",
    "product_type": "パンツ",
    "tags": "Men",
    "body_html": "<p>diesel pants</p>",
    "variants": [{"price": "22000", "available": True}],
    "images": [{"src": "https://cdn.example.test/diesel.jpg"}],
}


class _ReachHandler(BaseHTTPRequestHandler):
    hits: list[str]

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        self.hits.append(self.path)
        if path == "/robots.txt":
            self._send(200, ROBOTS, "text/plain")
            return
        if path == "/search":
            self._send(200, b'{"products":[]}', "application/json")
            return
        if path == "/sitemap.xml":
            body = (
                b"<?xml version='1.0'?><urlset>"
                b"<loc>http://127.0.0.1/products/8006002304964</loc>"
                b"</urlset>"
            )
            self._send(200, body, "application/xml")
            return
        if path.startswith("/collections/") and path.endswith("/products.json"):
            self._send(200, b'{"products":[]}', "application/json")
            return
        if path == "/products.json":
            self._send(
                200,
                json.dumps({"products": [PERSONSOUL, OTHER]}).encode("utf-8"),
                "application/json",
            )
            return
        self._send(404, b"missing", "text/plain")

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def reach_shop() -> Any:
    previous = os.environ.get("SEARCHER_ALLOW_LOOPBACK")
    os.environ["SEARCHER_ALLOW_LOOPBACK"] = "1"
    hits: list[str] = []

    class Bound(_ReachHandler):
        pass

    Bound.hits = hits
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Bound)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    try:
        yield f"http://{host}:{port}", hits
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
        if previous is None:
            os.environ.pop("SEARCHER_ALLOW_LOOPBACK", None)
        else:
            os.environ["SEARCHER_ALLOW_LOOPBACK"] = previous


def _install(base: str) -> str:
    host = urlparse(base).netloc
    name = "fixture_reach"

    class FixtureReachAdapter(ProductPageAdapter):
        def __init__(self) -> None:
            super().__init__(
                SourceSpec(
                    source_id=name,
                    adapter=name,
                    domain=host,
                    access_method="http_get",
                    admission=SourceAdmission.ADMITTED,
                    allowed_use="fixture reach",
                    source_class="vintage_archive",
                    robots_policy="Disallow: /search",
                    languages=("en", "ja"),
                    disallowed=("/search",),
                    listing_prefixes=("/products/",),
                    sitemap_urls=(f"{base.rstrip('/')}/sitemap.xml",),
                    collection_paths=("/collections/all",),
                    query_paths=("/collections/{slug}/products.json?limit=250",),
                    catalog_feed_path="/products.json",
                    origin=base.rstrip("/"),
                    rpm=120,
                )
            )

    ADAPTER_REGISTRY[name] = FixtureReachAdapter
    return name


def _remove(name: str) -> None:
    ADAPTER_REGISTRY.pop(name, None)


def test_slug_miss_still_finds_item_via_catalog_feed(
    controller: CampaignController, reach_shop: Any
) -> None:
    base, hits = reach_shop
    name = _install(base)
    try:
        intent = make_intent()
        intent = intent.model_copy(update={"text": "personsoul denim"})
        controller.create(intent, budget=make_budget())
        query = QueryVariant(
            query_id=new_id(),
            hypothesis_id="h",
            round=1,
            language="en",
            query_text="personsoul denim",
            query_type=QueryType.EXACT_NAME,
        )
        controller.repos.upsert_query(intent.search_id, query)
        engine = DiscoveryEngine(controller, max_work=16, batch_size=4)
        try:
            summary = engine.run(
                intent.search_id, [query], source_names=[name], include_disabled=True
            )
        finally:
            engine.close()
        urls = [item.canonical_url for item in summary.listings]
        assert urls, "catalog feed must find the item when the collection handle misses"
        assert any(url.endswith("/products/8072000111361") for url in urls)
        assert not any(url.endswith("/products/8006002304964") for url in urls)
        assert not any("/search" in hit for hit in hits)
        strategies = summary.strategy_coverage.get(name) or []
        by_name = {str(item.get("name")): item for item in strategies}
        assert COLLECTION_SLUG in by_name
        assert CATALOG_FEED in by_name
        assert SITE_SEARCH in by_name
        assert int(by_name[COLLECTION_SLUG].get("yielded") or 0) == 0
        assert int(by_name[CATALOG_FEED].get("yielded") or 0) >= 1
        assert by_name[SITE_SEARCH]["status"] in {"skipped", "blocked"}
        detail = summary.coverage_details.get(name) or ""
        assert "collection_slug" in detail
        assert "catalog_feed" in detail
        assert "site_search" in detail
        assert summary.candidates_after >= 1
        assert summary.coverage[name] == SourceOutcome.SEARCHED_MATCHES_FOUND.value
    finally:
        _remove(name)


def test_admission_and_robots_still_refuse_search_on_the_fixture_shop(
    controller: CampaignController, reach_shop: Any
) -> None:
    del controller
    base, hits = reach_shop
    name = _install(base)
    try:
        from searcher.sources.admission import AdmissionGate
        from searcher.sources.http import HonestHttpClient
        from searcher.sources.robots import RobotsCache

        adapter = ADAPTER_REGISTRY[name]()
        http = HonestHttpClient()
        try:
            gate = AdmissionGate(RobotsCache(user_agent=http.user_agent), http)
            decision = gate.decide(f"{base.rstrip('/')}/search?q=personsoul", adapter.manifest())
        finally:
            http.close()
        assert decision.allowed is False
        assert not any(urlparse(hit).path == "/search" for hit in hits)
    finally:
        _remove(name)


def _pick_kind_miss() -> tuple[str, str, str]:
    import json as json_mod
    import urllib.request

    from searcher.core.config import HONEST_USER_AGENT
    from searcher.sources.adapters.product import query_slugs, slugify_query

    def fetch(url: str) -> bytes:
        request = urllib.request.Request(
            url, headers={"User-Agent": HONEST_USER_AGENT, "Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()

    handles: set[str] = set()
    for page in range(1, 6):
        payload = json_mod.loads(
            fetch(f"https://shop.kind.co.jp/collections.json?limit=250&page={page}").decode("utf-8")
        )
        rows = payload.get("collections") or []
        if not rows:
            break
        for row in rows:
            if isinstance(row, dict) and row.get("handle"):
                handles.add(str(row["handle"]))
    products = json_mod.loads(
        fetch("https://shop.kind.co.jp/products.json?limit=250&page=1").decode("utf-8")
    ).get("products") or []
    for product in products:
        if not isinstance(product, dict):
            continue
        vendor = str(product.get("vendor") or "").strip()
        handle = str(product.get("handle") or "").strip()
        title = str(product.get("title") or "").strip()
        if not vendor or not handle:
            continue
        slugs = set(query_slugs(vendor) or [])
        slugs.add(slugify_query(vendor))
        if slugs & handles:
            continue
        return vendor, handle, title
    raise RuntimeError("kind.co.jp page 1 had no vendor without a collection handle")


# kind declares 12 requests per minute, so each of the 24 pages below is 5.0s of
# deliberate waiting: about 120s of politeness before anything else, and 230s
# measured end to end. The old 240s timeout left a 4% margin, which is why this
# passed alone and timed out inside the full suite where the shared host limiter
# is contended. Cutting the page budget instead was tried and does not work: at
# 8 pages the walk no longer reaches a vendor without a collection handle and
# the assertion fails honestly. The work is real and polite, so the timeout is
# what was wrong.
@pytest.mark.timeout(420)
def test_live_kind_finds_vendor_without_collection_handle(
    controller: CampaignController,
) -> None:
    try:
        vendor, handle, title = _pick_kind_miss()
    except Exception as exc:
        pytest.skip(f"kind.co.jp unreachable: {exc}")
    runner = LiveDiscoveryRunner(controller)
    intent = runner.create(
        vendor,
        language="en",
        extra_queries=[("ja", vendor)],
        wall_seconds=180,
        page_limit=24,
        source_limit=2,
        byte_limit=6_000_000,
    )
    summary = runner.run(intent.search_id, source_names=["kind"])
    assert summary is not None
    urls = [item.canonical_url for item in summary.listings]
    print("LIVE_KIND_VENDOR", vendor)
    print("LIVE_KIND_HANDLE", handle)
    print("LIVE_KIND_TITLE", title)
    print("LIVE_KIND_COVERAGE", summary.coverage)
    print("LIVE_KIND_DETAILS", summary.coverage_details)
    print("LIVE_KIND_STRATEGIES", summary.strategy_coverage)
    print("LIVE_KIND_BEFORE", summary.candidates_before)
    print("LIVE_KIND_AFTER", summary.candidates_after)
    print("LIVE_KIND_URLS", urls[:12])
    assert summary.coverage.get("kind") == SourceOutcome.SEARCHED_MATCHES_FOUND.value
    assert any("/products/" in url for url in urls)
    assert any(handle in url for url in urls) or any(
        vendor.casefold() in str(getattr(item.title, "value", "") or "").casefold()
        or vendor.casefold() in url.casefold()
        for item in summary.listings
        for url in (item.canonical_url,)
    )
    strategies = summary.strategy_coverage.get("kind") or []
    by_name = {str(item.get("name")): item for item in strategies}
    assert CATALOG_FEED in by_name
    assert int(by_name[CATALOG_FEED].get("yielded") or 0) >= 1
    collection = by_name.get(COLLECTION_SLUG)
    if collection is not None and collection.get("status") == "tried":
        assert int(collection.get("yielded") or 0) == 0
    detail = summary.coverage_details.get("kind") or ""
    assert "catalog_feed" in detail
    assert "site_search" in detail
