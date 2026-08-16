"""UTC-aware timestamps and monotonic durations. Naive datetimes are rejected."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator

from searcher.core.errors import NaiveDatetimeError


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise NaiveDatetimeError("naive datetime is not allowed")
    return value.astimezone(UTC)


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return ensure_utc(parsed)


def format_utc(value: datetime) -> str:
    return ensure_utc(value).isoformat()


UtcDateTime = Annotated[datetime, AfterValidator(ensure_utc)]


class MonotonicTimer:
    """Wall-independent duration measurement."""

    def __init__(self) -> None:
        self._start = time.monotonic()

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start
