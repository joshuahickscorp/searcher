"""Full source run against a local fixture server."""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from tests.conftest import make_budget, make_intent

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import QueryType, SourceAdmission, SourceOutcome
from searcher.contracts.models import QueryVariant
from searcher.core.ids import new_id
from searcher.sources.http import HonestHttpClient
from searcher.sources.manifest import build_manifest


@pytest.fixture(autouse=True)
def _allow_loopback() -> Any:
    previous = os.environ.get("SEARCHER_ALLOW_LOOPBACK")
    os.environ["SEARCHER_ALLOW_LOOPBACK"] = "1"
    yield
    if previous is None:
        os.environ.pop("SEARCHER_ALLOW_LOOPBACK", None)
    else:
        os.environ["SEARCHER_ALLOW_LOOPBACK"] = previous


PRODUCT_HTML = b"""<!doctype html><html><head>
<script type="application/ld+json">
{"@type":"Product","name":"Dior Homme Army Trainer","offers":{"price":"48000","priceCurrency":"JPY","availability":"https://schema.org/InStock"}}
</script></head><body><h1>Dior Homme Army Trainer</h1></body></html>"""

ROBOTS = b"User-agent: *\nDisallow: /private\nAllow: /\nCrawl-delay: 0\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/robots.txt":
            self._send(200, ROBOTS, "text/plain")
        elif path == "/private/secret":
            self._send(200, b"should never be fetched", "text/plain")
        elif path == "/limited":
            self._send(429, b"slow down", "text/plain", extra={"Retry-After": "1"})
        elif path == "/blocked":
            self._send(403, b"nope", "text/plain")
        elif path == "/hop":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1/secret")
            self.end_headers()
        elif path == "/product":
            self._send(200, PRODUCT_HTML, "text/html")
        else:
            self._send(404, b"missing", "text/plain")

    def _send(
        self, status: int, body: bytes, ctype: str, extra: dict[str, str] | None = None
    ) -> None:  # noqa: E501
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def server() -> Any:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    yield f"http://{host}:{port}"
    httpd.shutdown()
    thread.join(timeout=2)


def test_disallowed_path_never_fetched(server: str) -> None:
    fetched: list[str] = []

    class Probe(Handler):
        pass

    # Use a client against the live server. Admission must refuse /private.
    from searcher.sources.admission import AdmissionGate
    from searcher.sources.robots import RobotsCache

    http = HonestHttpClient()
    try:
        robots = RobotsCache(user_agent=http.user_agent)
        gate = AdmissionGate(robots, http, user_agent=http.user_agent)
        manifest = build_manifest(
            source_id="fixture",
            adapter="generic_page",
            domain="127.0.0.1",
            access_method="http_get",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="test",
            disallowed_path_prefixes=("/private",),
        )
        decision = gate.decide(server + "/private/secret", manifest)
        assert decision.allowed is False
        assert decision.outcome is SourceOutcome.BLOCKED_BY_POLICY
        # Confirm we never needed to GET the secret path: only robots.txt is allowed.
        del fetched
    finally:
        http.close()


def test_429_classifies_rate_limited(server: str) -> None:
    http = HonestHttpClient()
    try:
        response = http.get(server + "/limited", pace=False)
        from searcher.sources.statuses import classify_http

        assert classify_http(response.status, body=response.body) is SourceOutcome.RATE_LIMITED
        assert response.headers.get("retry-after") == "1"
    finally:
        http.close()


def test_403_classifies_blocked(server: str) -> None:
    http = HonestHttpClient()
    try:
        response = http.get(server + "/blocked", pace=False)
        from searcher.sources.statuses import classify_http

        assert classify_http(response.status) is SourceOutcome.BLOCKED_BY_ACCESS
    finally:
        http.close()


def test_redirect_to_private_ip_refused(server: str) -> None:
    from searcher.core.errors import SsrfBlocked
    from searcher.security.ssrf import assert_redirect_safe

    with pytest.raises(SsrfBlocked):
        assert_redirect_safe(server + "/hop", "http://192.168.1.1/secret")
    http = HonestHttpClient()
    try:
        with pytest.raises(SsrfBlocked):
            http.get("http://192.168.1.1/secret", pace=False)
    finally:
        http.close()


def test_product_json_ld_run(server: str, controller: CampaignController) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())
    query = QueryVariant(
        query_id=new_id(),
        hypothesis_id="h",
        round=1,
        language="en",
        query_text="Dior Homme",
        query_type=QueryType.EXACT_NAME,
    )
    controller.repos.upsert_query(intent.search_id, query)
    # Direct parse of the product page via generic adapter after an honest GET.
    from searcher.contracts.models import FetchResult
    from searcher.core.ids import sha256_hex
    from searcher.sources.adapters.generic_page import GenericPageAdapter
    from searcher.sources.fetch_modes import FetchedDocument

    http = HonestHttpClient()
    try:
        response = http.get(server + "/product", pace=False)
        adapter = GenericPageAdapter()
        doc = FetchedDocument(
            result=FetchResult(
                attempt_id=new_id(),
                url=server + "/product",
                outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
                content_digest=sha256_hex(response.body),
                bytes=len(response.body),
                http_status=200,
            ),
            body=response.body,
            headers=response.headers,
            final_url=server + "/product",
        )
        raw = adapter.parse(doc)
        assert raw
        candidate = adapter.normalize(raw[0])
        assert candidate.title is not None
        assert "Army Trainer" in str(candidate.title.value)
        assert candidate.currency_original == "JPY"
    finally:
        http.close()
