"""Rendering fetcher: robots, challenge, JS-only pages, optional extra."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from searcher.contracts.enums import FetchMode, SourceAdmission, SourceOutcome
from searcher.sources.admission import AdmissionGate
from searcher.sources.browser import BrowserPool, BrowserUnavailable, browser_extra_available
from searcher.sources.challenge import BLOCKED_BY_CHALLENGE, is_challenge_block
from searcher.sources.fetch_modes import Escalator
from searcher.sources.http import HonestHttpClient
from searcher.sources.manifest import build_manifest
from searcher.sources.robots import RobotsCache
from searcher.verification.extract import extract_structured

ROBOTS_DENY_PRIVATE = b"User-agent: *\nDisallow: /private\nAllow: /\nCrawl-delay: 0\n"

JS_ONLY = b"""<!doctype html><html><head><title></title></head><body>
<div id="root"></div>
<script>
var s = document.createElement('script');
s.type = 'application/ld+json';
s.textContent = JSON.stringify({
  "@type": "Product",
  "name": "JS Only Trainer",
  "brand": {"name": "Dior Homme"},
  "offers": {"price": "48000", "priceCurrency": "JPY",
             "availability": "https://schema.org/InStock"},
  "image": "https://shop.example/js.jpg"
});
document.head.appendChild(s);
var h = document.createElement('h1');
h.textContent = 'JS Only Trainer';
document.body.appendChild(h);
</script>
</body></html>"""

CHALLENGE_HTML = b"""<!doctype html><html><head><title>Just a moment...</title></head>
<body>Just a moment... cf-browser-verification</body></html>"""


class _State:
    def __init__(self) -> None:
        self.hits: dict[str, int] = {}
        self.secret_served = 0


STATE = _State()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        STATE.hits[path] = STATE.hits.get(path, 0) + 1
        if path == "/robots.txt":
            self._send(200, ROBOTS_DENY_PRIVATE, "text/plain")
        elif path == "/private/secret":
            STATE.secret_served += 1
            self._send(200, b"should never be fetched", "text/html")
        elif path == "/challenge":
            self._send(200, CHALLENGE_HTML, "text/html")
        elif path == "/js-only":
            self._send(200, JS_ONLY, "text/html")
        elif path == "/ok":
            body = (
                b'<!doctype html><html><head><script type="application/ld+json">'
                b'{"@type":"Product","name":"Plain Trainer"}'
                b"</script></head><body><h1>Plain Trainer</h1></body></html>"
            )
            self._send(200, body, "text/html")
        else:
            self._send(404, b"missing", "text/plain")

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(autouse=True)
def _loopback(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("SEARCHER_ALLOW_LOOPBACK", "1")
    yield
    if os.environ.get("SEARCHER_ALLOW_LOOPBACK") == "1":
        pass


@pytest.fixture
def server() -> Iterator[str]:
    STATE.hits.clear()
    STATE.secret_served = 0
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    yield f"http://{host}:{port}"
    httpd.shutdown()
    thread.join(timeout=2)


def _manifest() -> Any:
    return build_manifest(
        source_id="fixture_shop",
        adapter="generic_page",
        domain="127.0.0.1",
        access_method="http_get",
        admission_status=SourceAdmission.ADMITTED,
        allowed_use="local fixture",
        fetch_modes=[FetchMode.HTTP, FetchMode.LIGHT_RENDER, FetchMode.BROWSER],
    )


def _escalator(browsers: Any | None = None) -> Escalator:
    http = HonestHttpClient()
    return Escalator(
        http,
        AdmissionGate(RobotsCache(), http),
        cache=None,
        browsers=browsers,
    )


@dataclass
class FakeLease:
    kind: str
    content: str
    final_url: str
    status: int | None


@dataclass
class FakePool:
    calls: list[str] = field(default_factory=list)
    content: str = "<html><body>rendered</body></html>"
    status: int = 200
    raise_on_page: Exception | None = None

    @contextmanager
    def page(
        self, url: str, *, timeout_ms: int = 15000, light: bool = True
    ) -> Iterator[FakeLease]:
        self.calls.append(url)
        if self.raise_on_page is not None:
            raise self.raise_on_page
        yield FakeLease(
            kind="light" if light else "full",
            content=self.content,
            final_url=url,
            status=self.status,
        )

    def close(self) -> None:
        return None


def test_robots_disallow_is_refused_by_render_path(server: str) -> None:
    pool = FakePool()
    escalator = _escalator(pool)
    url = f"{server}/private/secret"
    doc = escalator.render(url, _manifest(), source_id="fixture_shop")
    assert doc.result.outcome is SourceOutcome.BLOCKED_BY_POLICY
    assert "robots" in (doc.result.classification_note or "").lower()
    assert pool.calls == []
    assert STATE.secret_served == 0
    via_fetch = escalator.fetch(
        url, _manifest(), source_id="fixture_shop", force_render=True
    )
    assert via_fetch.result.outcome is SourceOutcome.BLOCKED_BY_POLICY
    assert pool.calls == []
    assert STATE.secret_served == 0


def test_challenge_is_blocked_without_retry(server: str) -> None:
    pool = FakePool(content=CHALLENGE_HTML.decode("utf-8"))
    escalator = _escalator(pool)
    url = f"{server}/challenge"
    http_doc = escalator.fetch(url, _manifest(), source_id="fixture_shop")
    assert http_doc.result.outcome is SourceOutcome.BLOCKED_BY_ACCESS
    assert is_challenge_block(
        http_doc.result.classification_note, http_doc.result.error_class
    )
    assert (http_doc.result.classification_note or "").startswith(BLOCKED_BY_CHALLENGE)
    assert STATE.hits.get("/challenge") == 1
    render_doc = escalator.render(url, _manifest(), source_id="fixture_shop")
    assert render_doc.result.outcome is SourceOutcome.BLOCKED_BY_ACCESS
    assert is_challenge_block(
        render_doc.result.classification_note, render_doc.result.error_class
    )
    assert pool.calls == [url]


def test_js_only_page_empty_over_http(server: str) -> None:
    escalator = _escalator(None)
    url = f"{server}/js-only"
    doc = escalator.fetch(url, _manifest(), source_id="fixture_shop")
    html = doc.body.decode("utf-8", errors="replace")
    assert extract_structured(html, url) is None
    assert b'type="application/ld+json"' not in doc.body


def test_js_only_page_parses_under_renderer(server: str) -> None:
    if not browser_extra_available():
        pytest.skip("playwright extra is not installed")
    try:
        pool = BrowserPool(cap=1)
    except BrowserUnavailable as exc:
        pytest.skip(str(exc))
    escalator = _escalator(pool)
    url = f"{server}/js-only"
    try:
        plain = escalator.fetch(url, _manifest(), source_id="fixture_shop")
        assert extract_structured(plain.body.decode("utf-8", errors="replace"), url) is None
        rendered = escalator.render(url, _manifest(), source_id="fixture_shop")
        payload = extract_structured(
            rendered.body.decode("utf-8", errors="replace"), url
        )
        assert payload is not None
        assert payload["title"] == "JS Only Trainer"
        assert payload["price_original"] == "48000"
    finally:
        pool.close()
        escalator.http.close()


def test_absent_browser_extra_does_not_change_http_result(server: str) -> None:
    escalator = _escalator(None)
    url = f"{server}/ok"
    doc = escalator.fetch(url, _manifest(), source_id="fixture_shop", allow_render=True)
    assert doc.result.mode is FetchMode.HTTP
    assert doc.result.outcome is SourceOutcome.SEARCHED_MATCHES_FOUND
    escalator.http.close()


def test_browser_pool_closes_page_when_goto_raises() -> None:
    closed = {"page": 0, "context": 0}

    class FakePage:
        def goto(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("boom")

        def close(self) -> None:
            closed["page"] += 1

        def set_default_timeout(self, ms: int) -> None:
            return None

        @property
        def url(self) -> str:
            return "http://example.com"

        def content(self) -> str:
            return ""

    class FakeContext:
        def new_page(self) -> FakePage:
            return FakePage()

        def close(self) -> None:
            closed["context"] += 1

    class FakeBrowser:
        def new_context(self, **kwargs: object) -> FakeContext:
            return FakeContext()

    pool = BrowserPool()
    pool._ensure = lambda: FakeBrowser()  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="boom"), pool.page("http://example.com"):
        pass
    assert closed["page"] == 1
    assert closed["context"] == 1
    pool.close()
