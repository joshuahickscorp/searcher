"""Local HTTP shop used by orchestrator integration tests."""

from __future__ import annotations

import io
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urljoin, urlparse

from PIL import Image

from searcher.contracts.enums import FetchMode, SourceAdmission, SourceOutcome
from searcher.contracts.models import (
    ListingCandidate,
    LiveStatus,
    QueryVariant,
    RatePolicy,
    RawListing,
    SourceHealth,
    SourceManifest,
)
from searcher.core.ids import sha256_hex
from searcher.core.time import utc_now
from searcher.normalization.listing import normalize_raw
from searcher.sources.adapters.generic_page import (
    GenericPageAdapter,
    extract_listing,
    listing_links,
)
from searcher.sources.adapters.protocol import DiscoveryPageResult
from searcher.sources.fetch_modes import FetchedDocument
from searcher.sources.live_check import classify_liveness
from searcher.sources.manifest import build_manifest

BASE_URL = "http://127.0.0.1:0"


def tiny_png(color: tuple[int, int, int] = (40, 50, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(buf, format="PNG")
    return buf.getvalue()


PNG_ALPHA = tiny_png((30, 40, 50))
PNG_REPLICA = tiny_png((90, 20, 20))
PNG_JP = tiny_png((20, 60, 90))

ROBOTS = b"User-agent: *\nAllow: /\nCrawl-delay: 0\n"


def _product(name: str, sku: str, desc: str, image_path: str, extra: str = "") -> bytes:
    html = f"""<!doctype html><html><head>
<script type="application/ld+json">
{{"@type":"Product","name":"{name}","sku":"{sku}","description":"{desc}",
"image":"IMAGE","offers":{{"price":"480","priceCurrency":"EUR",
"availability":"https://schema.org/InStock"}}}}
</script></head><body><h1>{name}</h1><p>{desc}</p>{extra}
<img src="{image_path}" alt="{name}"></body></html>"""
    return html.encode("utf-8")


class ShopHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/robots.txt":
            self._send(200, ROBOTS, "text/plain")
        elif path == "/search":
            query = (parse_qs(parsed.query).get("q") or [""])[0]
            body = f"""<!doctype html><html><body>
<p>results for {query}</p>
<a href="/listing/alpha">Alpha Trainer SKU</a>
<a href="/listing/replica">Replica listing</a>
<a href="/listing/jp">Japanese listing</a>
</body></html>""".encode()
            self._send(200, body, "text/html")
        elif path == "/listing/alpha":
            html = _product(
                "Archive Alpha Trainer 2007",
                "ALPHASKU07",
                "Used archive trainer, original box.",
                "/img/alpha.png",
            )
            self._send(200, html.replace(b"IMAGE", b"/img/alpha.png"), "text/html")
        elif path == "/listing/replica":
            html = _product(
                "Unauthorized replica 1:1 of the original trainer",
                "REP-1",
                "This is a replica, not authentic.",
                "/img/replica.png",
            )
            self._send(200, html.replace(b"IMAGE", b"/img/replica.png"), "text/html")
        elif path == "/listing/jp":
            html = _product(
                "アーカイブ スニーカー 2007",
                "JP-SKU-07",
                "中古 アーカイブ",
                "/img/jp.png",
            )
            self._send(200, html.replace(b"IMAGE", b"/img/jp.png"), "text/html")
        elif path == "/img/alpha.png":
            self._send(200, PNG_ALPHA, "image/png")
        elif path == "/img/replica.png":
            self._send(200, PNG_REPLICA, "image/png")
        elif path == "/img/jp.png":
            self._send(200, PNG_JP, "image/png")
        else:
            self._send(404, b"missing", "text/plain")

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_shop() -> tuple[ThreadingHTTPServer, str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ShopHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    return httpd, f"http://{host}:{port}"


class OfflineShopAdapter:
    def __init__(self) -> None:
        host = urlparse(BASE_URL).netloc or "127.0.0.1"
        self._manifest = build_manifest(
            source_id="offline_shop",
            adapter="offline_shop",
            domain=host,
            access_method="http_get",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="offline fixture shop",
            source_class="consignment",
            languages=["en", "ja"],
            listing_path_prefixes=["/listing/"],
            fetch_modes=[FetchMode.CACHE, FetchMode.HTTP],
            rate_policy=RatePolicy(requests_per_minute=120, burst=8, concurrent=2),
        )
        self._generic = GenericPageAdapter(self._manifest)
        self.escalator = None

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        return SourceHealth(
            source_id="offline_shop",
            last_outcome=SourceOutcome.NOT_ATTEMPTED,
            last_checked_at=utc_now(),
        )

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del cursor
        url = f"{BASE_URL}/search?q={query.query_text}"
        return DiscoveryPageResult([url], [], None, SourceOutcome.NOT_ATTEMPTED.value, "seeds")

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        if fetch.result.outcome is not SourceOutcome.SEARCHED_MATCHES_FOUND:
            return []
        html = fetch.body.decode("utf-8", errors="replace")
        url = fetch.final_url or fetch.result.url
        if "/listing/" in url:
            payload = extract_listing(html, url)
            images = []
            for img in payload.get("images") or []:
                if isinstance(img, str):
                    images.append({"url": urljoin(url, img)})
                elif isinstance(img, dict) and img.get("url"):
                    images.append({**img, "url": urljoin(url, str(img["url"]))})
            payload["images"] = images
            return [
                RawListing(
                    source_adapter="offline_shop",
                    url=url,
                    payload=payload,
                    content_digest=fetch.result.content_digest or sha256_hex(fetch.body),
                    fetched_at=utc_now(),
                )
            ]
        return []

    def normalize(self, raw: RawListing) -> ListingCandidate:
        return normalize_raw(raw)

    def live_check(self, candidate: ListingCandidate) -> LiveStatus:
        return classify_liveness(
            http_status=200,
            body="live listing page " * 40,
            outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
        )

    def listing_urls_from(self, html: str, url: str) -> list[str]:
        return listing_links(html, url, ["/listing/"])


def install_offline_adapter(base_url: str) -> None:
    global BASE_URL
    BASE_URL = base_url
    from searcher.sources.adapters import ADAPTER_REGISTRY

    ADAPTER_REGISTRY["offline_shop"] = OfflineShopAdapter


def remove_offline_adapter() -> None:
    from searcher.sources.adapters import ADAPTER_REGISTRY

    ADAPTER_REGISTRY.pop("offline_shop", None)
