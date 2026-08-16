"""§6.5 / §17.1 URL canonicalization and tracking-parameter removal."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "fbclid",
        "gclid",
        "gclsrc",
        "dclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "igshid",
        "spm",
        "ref",
        "ref_",
        "referrer",
        "affiliate",
        "aff",
        "aff_id",
        "clickid",
        "cmpid",
        "campaign",
        "src",
        "source",
        "_ga",
        "_gl",
        "ncid",
        "icid",
    }
)

LISTING_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"/itm/(\d+)", re.I),
    re.compile(r"/listing/(\d+)", re.I),
    re.compile(r"/items/([A-Za-z0-9_-]+)", re.I),
    re.compile(r"/products/([A-Za-z0-9_-]+)", re.I),
    re.compile(r"/product/([A-Za-z0-9_-]+)", re.I),
    re.compile(r"/p/([A-Za-z0-9_-]+)", re.I),
    re.compile(r"/shop/.+/products/([A-Za-z0-9_-]+)", re.I),
    re.compile(r"/products/detail/([A-Za-z0-9_-]+)", re.I),
    re.compile(r"/auction/([A-Za-z0-9_-]+)", re.I),
    re.compile(r"[?&]id=(\d+)"),
)


def looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    if not host:
        return url.strip()
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    query_pairs.sort()
    query = urlencode(query_pairs, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def extract_listing_id(url: str) -> str | None:
    for pattern in LISTING_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()
