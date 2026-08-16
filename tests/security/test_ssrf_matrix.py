"""SSRF matrix, scheme matrix, redirect re-validation, size and decompression."""

from __future__ import annotations

import os

import httpx
import pytest

from searcher.core.errors import SsrfBlocked
from searcher.security.limits import (
    DecompressionBomb,
    ResponseTooLarge,
    check_byte_budget,
    check_decompression,
)
from searcher.security.ssrf import assert_redirect_safe, assert_url_safe
from searcher.sources.http import HonestHttpClient


@pytest.fixture(autouse=True)
def _deny_loopback() -> None:
    previous = os.environ.pop("SEARCHER_ALLOW_LOOPBACK", None)
    yield
    if previous is not None:
        os.environ["SEARCHER_ALLOW_LOOPBACK"] = previous


BLOCKED_URLS = (
    "file:///etc/passwd",
    "data:text/html,hi",
    "ftp://example.com/a",
    "http://localhost/admin",
    "http://127.0.0.1/",
    "http://[::1]/",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.1/",
    "http://192.168.1.1/",
    "http://172.16.0.1/",
    "http://metadata.google.internal/",
)


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_blocked_urls_refused(url: str) -> None:
    with pytest.raises(SsrfBlocked):
        assert_url_safe(url, resolve=False)


def test_https_public_host_allowed() -> None:
    safety = assert_url_safe("https://example.com/path", resolve=False)
    assert safety.scheme == "https"
    assert safety.host == "example.com"


def test_redirect_into_private_refused() -> None:
    with pytest.raises(SsrfBlocked):
        assert_redirect_safe("https://example.com/out", "http://127.0.0.1/secret")
    with pytest.raises(SsrfBlocked):
        assert_redirect_safe("https://example.com/out", "http://192.168.0.5/x")


def test_real_request_to_loopback_refused() -> None:
    client = HonestHttpClient(timeout=2.0)
    try:
        with pytest.raises(SsrfBlocked):
            client.get("http://127.0.0.1:9/", pace=False)
    finally:
        client.close()


def test_redirect_revalidation_on_real_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        return httpx.Response(200, content=b"ok")

    transport = httpx.MockTransport(handler)
    client = HonestHttpClient(transport=transport)
    try:
        with pytest.raises(SsrfBlocked):
            client.get("https://example.com/start", pace=False)
    finally:
        client.close()


def test_response_size_limit() -> None:
    with pytest.raises(ResponseTooLarge):
        check_byte_budget(10_000_000, 1_000)


def test_decompression_bomb_limit() -> None:
    with pytest.raises(DecompressionBomb):
        check_decompression(declared_length=2000, actual=2000 * 80)


def test_client_aborts_oversized_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, content=b"x" * 5000)

    transport = httpx.MockTransport(handler)
    client = HonestHttpClient(transport=transport, max_bytes=100)
    try:
        with pytest.raises(ResponseTooLarge):
            client.get("https://example.com/big", pace=False)
    finally:
        client.close()
