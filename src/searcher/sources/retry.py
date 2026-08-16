# Ported idea from Job Scraper frozen snapshot
# path: $SEARCHER_JOBSCRAPER_FROZEN_DIR/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.http_client.HttpClient.get_json retry block
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
"""Cause-specific retry. 403/challenge is terminal. Retry-After capped at 60s."""

from __future__ import annotations

import random
from email.utils import parsedate_to_datetime

from searcher.contracts.enums import SourceOutcome
from searcher.sources.statuses import classify_http

RETRY_CEILING = 4
RETRY_AFTER_CAP = 60.0
BACKOFF_BASE = 1.0
BACKOFF_MAX = 30.0


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    stripped = value.strip()
    try:
        seconds = float(stripped)
    except ValueError:
        try:
            when = parsedate_to_datetime(stripped)
        except (TypeError, ValueError):
            return None
        delta = (
            when.timestamp() - parsedate_to_datetime("Thu, 01 Jan 1970 00:00:00 GMT").timestamp()
        )  # noqa: E501
        # parsedate_to_datetime already gives an aware or naive datetime; use now via seconds.
        from datetime import UTC, datetime

        aware = when if when.tzinfo else when.replace(tzinfo=UTC)
        seconds = float((aware - datetime.now(UTC)).total_seconds())
        del delta
    if seconds < 0:
        return 0.0
    return min(float(seconds), RETRY_AFTER_CAP)


def backoff_seconds(attempt: int, retry_after: float | None = None) -> float:
    if retry_after is not None:
        return min(retry_after, RETRY_AFTER_CAP)
    exp = min(BACKOFF_MAX, BACKOFF_BASE * (2 ** max(0, attempt - 1)))
    jitter = random.uniform(0.0, 0.4 * exp)
    return float(min(BACKOFF_MAX, exp + jitter))


def should_retry(
    outcome: SourceOutcome, attempt: int, *, retry_ceiling: int = RETRY_CEILING
) -> bool:  # noqa: E501
    if attempt >= retry_ceiling:
        return False
    return outcome in {
        SourceOutcome.RATE_LIMITED,
        SourceOutcome.NETWORK_FAILED,
        SourceOutcome.SOURCE_UNAVAILABLE,
    }


def classify_response(
    status: int | None,
    body: bytes | str | None = None,
    *,
    challenge: bool = False,
) -> SourceOutcome:
    return classify_http(status, body=body, challenge=challenge)
