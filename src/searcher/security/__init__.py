"""Network security: SSRF, size, redirect, and decompression bounds."""

from __future__ import annotations

from searcher.security.limits import (
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_PAGES,
    DEFAULT_MAX_REDIRECTS,
    DecompressionBomb,
    RedirectLimitExceeded,
    ResponseTooLarge,
    check_byte_budget,
    check_decompression,
    check_redirect_budget,
)
from searcher.security.ssrf import (
    ALLOWED_SCHEMES,
    UrlSafety,
    assert_redirect_safe,
    assert_url_safe,
    join_redirect,
)

__all__ = [
    "ALLOWED_SCHEMES",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_PAGES",
    "DEFAULT_MAX_REDIRECTS",
    "DecompressionBomb",
    "RedirectLimitExceeded",
    "ResponseTooLarge",
    "UrlSafety",
    "assert_redirect_safe",
    "assert_url_safe",
    "check_byte_budget",
    "check_decompression",
    "check_redirect_budget",
    "join_redirect",
]
