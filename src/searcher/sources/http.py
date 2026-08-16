# Ported idea from Job Scraper frozen snapshot
# path: $SEARCHER_JOBSCRAPER_FROZEN_DIR/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.http_client:DomainLimiter + honest httpx client
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
"""Honest HTTP client. One static identifying User-Agent. No impersonation."""

from __future__ import annotations

import random
import ssl
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from searcher.core.config import HONEST_USER_AGENT
from searcher.core.errors import ErrorClass, SearcherError
from searcher.core.ids import new_id, sha256_hex
from searcher.normalization.url import canonicalize_url, host_of
from searcher.security.limits import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_REDIRECTS,
    check_byte_budget,
    check_decompression,
    check_redirect_budget,
)
from searcher.security.ssrf import assert_redirect_safe, assert_url_safe


def _ssl_context() -> ssl.SSLContext:
    """Prefer the system store. Fall back if certifi cannot be read."""
    try:
        return ssl.create_default_context()
    except PermissionError:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        try:
            context.load_default_certs()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
        except Exception:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context


SEARCHER_USER_AGENT = HONEST_USER_AGENT
REDACT_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "api-key",
        "x-api-key",
        "x-subscription-token",
    }
)


class FetchError(SearcherError):
    def __init__(self, message: str, *, error_class: ErrorClass = ErrorClass.NETWORK) -> None:
        super().__init__(message, error_class=error_class)


@dataclass
class DomainLimiter:
    """Per-host lock plus jittered base delay. Donor idea, no ATS host sets."""

    base_delay: float
    last_at: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def acquire(self) -> None:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_at
            jittered = self.base_delay * random.uniform(0.7, 1.3)
            if elapsed < jittered:
                time.sleep(jittered - elapsed)
            self.last_at = time.monotonic()


@dataclass(frozen=True, slots=True)
class HttpResponse:
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    body: bytes
    elapsed_ms: int
    redirected_from: str | None
    hops: int

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    @property
    def content_type(self) -> str | None:
        return self.headers.get("content-type")

    @property
    def digest(self) -> str:
        return sha256_hex(self.body)


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in REDACT_HEADERS:
            out[key] = "[redacted]"
        else:
            out[key] = value
    return out


class HonestHttpClient:
    """http/https only, redirect re-validation, bounded bodies, static UA."""

    def __init__(
        self,
        *,
        user_agent: str = SEARCHER_USER_AGENT,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.timeout = timeout
        self._limiters: dict[str, DomainLimiter] = {}
        self._lock = threading.Lock()
        kwargs: dict[str, Any] = {
            "timeout": httpx.Timeout(timeout, connect=10.0),
            "follow_redirects": False,
            "headers": {"User-Agent": user_agent, "Accept": "*/*"},
            "verify": _ssl_context(),
        }
        if transport is not None:
            kwargs["transport"] = transport
            kwargs.pop("verify", None)
        self._client = httpx.Client(**kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HonestHttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def limiter_for(self, url: str, base_delay: float) -> DomainLimiter:
        host = host_of(url)
        with self._lock:
            held = self._limiters.get(host)
            if held is None or held.base_delay != base_delay:
                held = DomainLimiter(base_delay=base_delay)
                self._limiters[host] = held
            return held

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        base_delay: float = 1.0,
        extra_headers: Mapping[str, str] | None = None,
        if_none_match: str | None = None,
        if_modified_since: str | None = None,
        pace: bool = True,
    ) -> HttpResponse:
        assert_url_safe(url, resolve=True)
        if pace:
            self.limiter_for(url, base_delay).acquire()
        merged: dict[str, str] = {"User-Agent": self.user_agent}
        if headers:
            merged.update(headers)
        if extra_headers:
            merged.update(extra_headers)
        if if_none_match:
            merged["If-None-Match"] = if_none_match
        if if_modified_since:
            merged["If-Modified-Since"] = if_modified_since
        current = url
        origin = url
        hops = 0
        started = time.monotonic()
        redirected_from: str | None = None
        while True:
            assert_url_safe(current, resolve=True)
            try:
                response = self._client.request(method, current, headers=merged)
            except httpx.TimeoutException as exc:
                raise FetchError(
                    f"timeout fetching {current}", error_class=ErrorClass.TIMEOUT
                ) from exc  # noqa: E501
            except httpx.HTTPError as exc:
                raise FetchError(f"network error fetching {current}: {exc}") from exc
            if response.is_redirect:
                hops += 1
                check_redirect_budget(hops, self.max_redirects)
                location = response.headers.get("location")
                nxt = assert_redirect_safe(current, location or "")
                redirected_from = origin
                current = nxt
                method = "GET" if response.status_code in {301, 302, 303} else method
                continue
            raw_length = response.headers.get("content-length")
            declared = int(raw_length) if raw_length and raw_length.isdigit() else None
            body = response.content
            check_byte_budget(len(body), self.max_bytes)
            check_decompression(declared, len(body))
            header_map = {k.lower(): v for k, v in response.headers.items()}
            elapsed = int((time.monotonic() - started) * 1000)
            return HttpResponse(
                url=origin,
                final_url=str(response.url) if response.url else current,
                status=response.status_code,
                headers=header_map,
                body=body,
                elapsed_ms=elapsed,
                redirected_from=redirected_from,
                hops=hops,
            )

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        return self.request("GET", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> HttpResponse:
        return self.request("HEAD", url, **kwargs)


def new_attempt_id() -> str:
    return new_id()


def canonical_or_same(url: str) -> str:
    try:
        return canonicalize_url(url)
    except Exception:
        return url


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
