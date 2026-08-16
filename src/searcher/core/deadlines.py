"""Connect, read, and per-source deadlines for outbound work.

Campaign stages that talk to the network inherit these ceilings. A source
that cannot finish inside the per-source budget is recorded and skipped.
These are deadlines, not campaign budget cuts: sealed page/source/wall
ceilings stay where the campaign sealed them.
"""

from __future__ import annotations

import os

CONNECT_TIMEOUT_SECONDS = 5.0
READ_TIMEOUT_SECONDS = 15.0
REQUEST_TIMEOUT_SECONDS = 12.0
SOURCE_DEADLINE_SECONDS = 20.0
RETRY_REMAINING_FLOOR_SECONDS = 0.05


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def connect_timeout_seconds() -> float:
    return max(0.05, _env_float("SEARCHER_CONNECT_TIMEOUT_SECONDS", CONNECT_TIMEOUT_SECONDS))


def request_timeout_seconds() -> float:
    return max(0.05, _env_float("SEARCHER_FETCH_TIMEOUT_SECONDS", REQUEST_TIMEOUT_SECONDS))


def source_deadline_seconds() -> float:
    return max(0.2, _env_float("SEARCHER_SOURCE_DEADLINE_SECONDS", SOURCE_DEADLINE_SECONDS))


default_request_timeout = request_timeout_seconds
default_source_deadline = source_deadline_seconds
