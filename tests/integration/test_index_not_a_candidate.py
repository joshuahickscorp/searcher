"""A campaign served an index must emit product candidates, never the index URL."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from tests.conftest import make_budget, make_intent

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import QueryType, SourceAdmission
from searcher.contracts.models import QueryVariant
from searcher.core.ids import new_id
from searcher.sources.adapters import ADAPTER_REGISTRY
from searcher.sources.adapters.product import ProductPageAdapter, SourceSpec
from searcher.sources.engine import DiscoveryEngine
from searcher.sources.expand import IMAGES_MISSING_KEY

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "shopify" / "name_willy_products.json"
INDEX_PATH = "/collections/name-willy/products.json"
ROBOTS = b"User-agent: *\nAllow: /\nCrawl-delay: 0\n"


class _IndexHandler(BaseHTTPRequestHandler):
    body = FIXTURE.read_bytes()

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/robots.txt":
            self._send(200, ROBOTS, "text/plain")
            return
        if path == INDEX_PATH:
            self._send(200, self.body, "application/json")
            return
        self._send(404, b"missing", "text/plain")

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def index_server() -> Any:
    previous = os.environ.get("SEARCHER_ALLOW_LOOPBACK")
    os.environ["SEARCHER_ALLOW_LOOPBACK"] = "1"
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _IndexHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
        if previous is None:
            os.environ.pop("SEARCHER_ALLOW_LOOPBACK", None)
        else:
            os.environ["SEARCHER_ALLOW_LOOPBACK"] = previous


def _install_adapter(base: str) -> str:
    host = urlparse(base).netloc
    name = "fixture_index"

    class FixtureIndexAdapter(ProductPageAdapter):
        def __init__(self) -> None:
            super().__init__(
                SourceSpec(
                    source_id=name,
                    adapter=name,
                    domain=host,
                    access_method="http_get",
                    admission=SourceAdmission.ADMITTED,
                    allowed_use="fixture index expansion",
                    source_class="vintage_archive",
                    robots_policy="Allow /",
                    languages=("en",),
                    disallowed=(),
                    listing_prefixes=("/products/",),
                    query_paths=(),
                    collection_paths=(),
                    rpm=120,
                )
            )
            self.base = base.rstrip("/")

        def discover(self, query: QueryVariant, cursor: str | None) -> Any:
            from searcher.contracts.enums import SourceOutcome
            from searcher.sources.adapters.protocol import DiscoveryPageResult

            del query, cursor
            return DiscoveryPageResult(
                [f"{self.base}{INDEX_PATH}?limit=250"],
                [],
                None,
                SourceOutcome.NOT_ATTEMPTED.value,
                "query",
            )

    ADAPTER_REGISTRY[name] = FixtureIndexAdapter
    return name


def _remove_adapter(name: str) -> None:
    ADAPTER_REGISTRY.pop(name, None)


def test_campaign_served_index_emits_product_candidates_only(
    controller: CampaignController, index_server: str
) -> None:
    name = _install_adapter(index_server)
    try:
        intent = make_intent()
        controller.create(intent, budget=make_budget())
        query = QueryVariant(
            query_id=new_id(),
            hypothesis_id="h",
            round=1,
            language="en",
            query_text="Willy Chavarria",
            query_type=QueryType.EXACT_NAME,
        )
        controller.repos.upsert_query(intent.search_id, query)
        engine = DiscoveryEngine(
            controller,
            max_work=20,
            batch_size=4,
            per_index_cap=24,
            per_campaign_cap=48,
        )
        try:
            summary = engine.run(
                intent.search_id, [query], source_names=[name], include_disabled=True
            )
        finally:
            engine.close()
        urls = [item.canonical_url for item in summary.listings]
        assert urls, "expected product candidates from the collection feed"
        assert not any("products.json" in url for url in urls)
        assert not any("/collections/" in url for url in urls)
        assert not any(url.rstrip("/").endswith("sitemap") for url in urls)
        assert all("/products/" in url for url in urls)
        expected = [
            item["handle"] for item in json.loads(FIXTURE.read_text(encoding="utf-8"))["products"]
        ]
        for handle in expected:
            assert any(url.endswith(f"/products/{handle}") for url in urls)
        pictured = [item for item in summary.listings if item.images]
        assert pictured, "feed products with images must keep those image URLs"
        bare = [
            item
            for item in summary.listings
            if item.canonical_url.endswith("/products/8001001149999")
        ]
        assert bare
        assert bare[0].images == []
        assert bare[0].structured_data.get(IMAGES_MISSING_KEY) == "feed_listed_no_images"
        expansions = list(summary.expansions) or list(
            controller.repos.get_runtime(intent.search_id).get("index_expansions") or []
        )
        assert expansions
        first = expansions[0]
        assert int(first["members_found"]) == len(expected)
        assert int(first["taken"]) == len(expected)
        assert "dropped" in first
        assert first.get("drop_reasons") is not None
        receipts = controller.repos.list_receipts(intent.search_id)
        assert any(row.get("receipt_type") == "IndexExpansionReceipt" for row in receipts)
    finally:
        _remove_adapter(name)
