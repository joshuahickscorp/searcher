# Ported idea from Job Scraper frozen snapshot
# path: $SEARCHER_JOBSCRAPER_FROZEN_DIR/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.fetchers.base:strip_html / parse_iso_date
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
"""HTML text crush and listing-date parsing."""

from __future__ import annotations

import html
import re
from datetime import date, datetime
from typing import Any

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%b %d, %Y",
    "%d %b %Y",
)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _TAG_RE.sub(" ", value)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None
