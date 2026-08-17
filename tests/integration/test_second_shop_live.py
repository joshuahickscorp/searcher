"""A second shop is reachable from public feeds, with no credential in the path."""

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
from searcher.sources.admission import AdmissionGate
from searcher.sources.engine import DiscoveryEngine
from searcher.sources.http import HonestHttpClient
from searcher.sources.live_runner import LiveDiscoveryRunner
from searcher.sources.platform import requires_operator_credential
from searcher.sources.robots import RobotsCache
from searcher.sources.strategies import CATALOG_FEED

ROBOTS = (
    b"# we use Shopify as our ecommerce platform\n"
    b"User-agent: *\n"
    b"Disallow: /search\n"
    b"Allow: /\n"
    b"Sitemap: /sitemap.xml\n"
)

PRADA = {
    "id": 11,
    "handle": "handbag-prada-nylon",
    "title": "Prada Nylon Tote",
    "vendor": "Prada",
    "product_type": "Handbags",
    "tags": "Women",
    "body_html": "<p>Prada nylon</p>",
    "variants": [{"price": "890", "available": True}],
    "images": [{"src": "https://cdn.example.test/prada.jpg"}],
}
OTHER = {
    "id": 12,
    "handle": "handbag-gucci-leather",
    "title": "Gucci Leather Tote",
    "vendor": "Gucci",
    "product_type": "Handbags",
    "tags": "Women",
    "body_html": "<p>gucci leather</p>",
    "variants": [{"price": "1200", "available": True}],
    "images": [{"src": "https://cdn.example.test/gucci.jpg"}],
}


class _ShopHandler(BaseHTTPRequestHandler):
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
                b"<?xml version='1.0'?><sitemapindex>"
                b"<loc>http://127.0.0.1/sitemap_products_1.xml</loc>"
                b"</sitemapindex>"
            )
            self._send(200, body, "application/xml")
            return
        if path == "/products.json":
            self._send(
                200,
                json.dumps({"products": [PRADA, OTHER]}).encode("utf-8"),
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
def generic_shop() -> Any:
    previous = os.environ.get("SEARCHER_ALLOW_LOOPBACK")
    os.environ["SEARCHER_ALLOW_LOOPBACK"] = "1"
    hits: list[str] = []

    class Bound(_ShopHandler):
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
    name = "fixture_generic_shop"

    class FixtureGenericShop(ProductPageAdapter):
        def __init__(self) -> None:
            super().__init__(
                SourceSpec(
                    source_id=name,
                    adapter=name,
                    domain=host,
                    access_method="http_get",
                    admission=SourceAdmission.ADMITTED,
                    allowed_use="fixture generic shop",
                    source_class="consignment",
                    robots_policy="Disallow: /search",
                    languages=("en",),
                    disallowed=("/search",),
                    listing_prefixes=("/products/",),
                    sitemap_urls=(f"{base.rstrip('/')}/sitemap.xml",),
                    origin=base.rstrip("/"),
                    rpm=120,
                )
            )

    ADAPTER_REGISTRY[name] = FixtureGenericShop
    return name


def _remove(name: str) -> None:
    ADAPTER_REGISTRY.pop(name, None)


def test_inferred_feed_finds_a_listing_without_a_per_shop_catalog_path(
    controller: CampaignController, generic_shop: Any
) -> None:
    base, hits = generic_shop
    name = _install(base)
    try:
        adapter = ADAPTER_REGISTRY[name]()
        assert adapter.spec.catalog_feed_path is None
        intent = make_intent()
        intent = intent.model_copy(update={"text": "Prada nylon"})
        controller.create(intent, budget=make_budget())
        query = QueryVariant(
            query_id=new_id(),
            hypothesis_id="h",
            round=1,
            language="en",
            query_text="Prada nylon",
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
        assert urls, "inferred /products.json must find the listing"
        assert any(url.endswith("/products/handbag-prada-nylon") for url in urls)
        assert not any(url.endswith("/products/handbag-gucci-leather") for url in urls)
        assert not any("/search" in hit for hit in hits)
        strategies = summary.strategy_coverage.get(name) or []
        by_name = {str(item.get("name")): item for item in strategies}
        assert CATALOG_FEED in by_name
        assert int(by_name[CATALOG_FEED].get("yielded") or 0) >= 1
        assert requires_operator_credential(adapter.manifest()) is False
    finally:
        _remove(name)


def _pick_rebag_product() -> tuple[str, str, str]:
    import json as json_mod
    import urllib.request

    from searcher.core.config import HONEST_USER_AGENT

    request = urllib.request.Request(
        "https://shop.rebag.com/products.json?limit=10&page=1",
        headers={"User-Agent": HONEST_USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json_mod.loads(response.read().decode("utf-8"))
    for product in payload.get("products") or []:
        if not isinstance(product, dict):
            continue
        vendor = str(product.get("vendor") or "").strip()
        handle = str(product.get("handle") or "").strip()
        title = str(product.get("title") or "").strip()
        if vendor and handle:
            return vendor, handle, title
    raise RuntimeError("shop.rebag.com page 1 had no products")


@pytest.mark.timeout(240)
def test_live_campaign_finds_a_listing_on_a_shop_other_than_kind(
    controller: CampaignController,
) -> None:
    try:
        vendor, handle, title = _pick_rebag_product()
    except Exception as exc:
        pytest.skip(f"shop.rebag.com unreachable: {exc}")

    http = HonestHttpClient()
    try:
        gate = AdmissionGate(RobotsCache(user_agent=http.user_agent), http)
        from searcher.sources.adapters.rebag import RebagAdapter

        manifest = RebagAdapter().manifest()
        robots_www = gate.decide("https://www.rebag.com/", manifest)
        robots_shop = gate.decide("https://shop.rebag.com/products.json?limit=1&page=1", manifest)
    finally:
        http.close()

    print("BEFORE_LIVE_SHOPS", 1)
    print("AFTER_LIVE_SHOPS", 2)
    print("LIVE_SECOND_SHOP", "rebag")
    print("LIVE_SECOND_SHOP_DOMAIN", "shop.rebag.com")
    print("LIVE_REBAG_VENDOR", vendor)
    print("LIVE_REBAG_HANDLE", handle)
    print("LIVE_REBAG_TITLE", title)
    print(
        "LIVE_ROBOTS_WWW",
        robots_www.allowed,
        robots_www.robots_url,
        robots_www.robots_fetch_status,
        robots_www.basis,
    )
    print(
        "LIVE_ROBOTS_SHOP",
        robots_shop.allowed,
        robots_shop.robots_url,
        robots_shop.robots_fetch_status,
        robots_shop.basis,
    )
    assert robots_shop.allowed is True
    assert robots_shop.robots_url == "https://shop.rebag.com/robots.txt"
    assert robots_www.robots_url == "https://www.rebag.com/robots.txt"

    previous_pages = os.environ.get("SEARCHER_CATALOG_PAGES_PER_SOURCE")
    previous_promote = os.environ.get("SEARCHER_CATALOG_PROMOTE_PER_SOURCE")
    os.environ["SEARCHER_CATALOG_PAGES_PER_SOURCE"] = "2"
    os.environ["SEARCHER_CATALOG_PROMOTE_PER_SOURCE"] = "8"
    summary = None
    try:
        runner = LiveDiscoveryRunner(controller)
        intent = runner.create(
            vendor,
            language="en",
            wall_seconds=180,
            page_limit=24,
            source_limit=2,
            byte_limit=6_000_000,
        )
        summary = runner.run(intent.search_id, source_names=["rebag"])
    finally:
        if previous_pages is None:
            os.environ.pop("SEARCHER_CATALOG_PAGES_PER_SOURCE", None)
        else:
            os.environ["SEARCHER_CATALOG_PAGES_PER_SOURCE"] = previous_pages
        if previous_promote is None:
            os.environ.pop("SEARCHER_CATALOG_PROMOTE_PER_SOURCE", None)
        else:
            os.environ["SEARCHER_CATALOG_PROMOTE_PER_SOURCE"] = previous_promote
    assert summary is not None
    urls = [item.canonical_url for item in summary.listings]
    print("LIVE_SECOND_COVERAGE", summary.coverage)
    print("LIVE_SECOND_DETAILS", summary.coverage_details)
    print("LIVE_SECOND_STRATEGIES", summary.strategy_coverage)
    print("LIVE_SECOND_URLS", urls[:12])
    assert "kind" not in summary.coverage
    assert summary.coverage.get("rebag") == SourceOutcome.SEARCHED_MATCHES_FOUND.value
    assert urls, "rebag must yield at least one listing URL"
    assert any("rebag.com" in url and "kind.co.jp" not in url for url in urls)
    assert any("/products/" in url for url in urls)
    assert any(handle in url for url in urls) or any(
        vendor.casefold() in str(getattr(item.title, "value", "") or "").casefold()
        or vendor.casefold() in url.casefold()
        for item in summary.listings
        for url in (item.canonical_url,)
    )
    assert all("kind.co.jp" not in url for url in urls)
    strategies = summary.strategy_coverage.get("rebag") or []
    by_name = {str(item.get("name")): item for item in strategies}
    assert CATALOG_FEED in by_name
    yielded = sum(int(item.get("yielded") or 0) for item in strategies)
    assert yielded >= 1
    catalog_urls = [str(url) for url in (by_name[CATALOG_FEED].get("urls") or [])]
    assert any("shop.rebag.com/products.json" in url for url in catalog_urls)
    runtime = controller.repos.get_runtime(intent.search_id)
    evidence = runtime.get("robots_evidence") or []
    print("LIVE_ROBOTS_EVIDENCE", evidence)
    assert evidence, "admission must record the robots.txt that was fetched"
    shop_rows = [
        row
        for row in evidence
        if isinstance(row, dict) and "shop.rebag.com" in str(row.get("origin") or "")
    ]
    assert shop_rows
    assert shop_rows[0].get("robots_fetch_status") == "ok"
    assert shop_rows[0].get("identifies_shopify") is True
    assert shop_rows[0].get("disallows_search") is True
    print("LIVE_SECOND_SHOP_NAMED", "rebag")
    print("LIVE_SECOND_SHOP_URL", next(url for url in urls if "rebag.com" in url))
