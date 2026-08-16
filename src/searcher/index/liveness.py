"""Stale liveness is unverified. It is never presented as live (§16.4, §3.10)."""

from __future__ import annotations

from datetime import datetime, timedelta

from searcher.contracts.enums import Availability
from searcher.contracts.models import ListingCandidate
from searcher.core.time import utc_now


def liveness_expired(
    last_checked_at: datetime, *, ttl_seconds: int, now: datetime | None = None
) -> bool:
    checked = last_checked_at
    if checked.tzinfo is None or (now is not None and now.tzinfo is None):
        return True
    current = now or utc_now()
    return current - checked > timedelta(seconds=max(0, ttl_seconds))


def present_availability(
    stored: Availability,
    last_checked_at: datetime,
    *,
    ttl_seconds: int,
    now: datetime | None = None,
) -> Availability:
    """Expired or missing checks read as UNKNOWN, never LIVE."""
    if liveness_expired(last_checked_at, ttl_seconds=ttl_seconds, now=now):
        return Availability.UNKNOWN
    return stored


def apply_liveness_ttl(
    candidate: ListingCandidate,
    *,
    ttl_seconds: int,
    now: datetime | None = None,
) -> ListingCandidate:
    presented = present_availability(
        candidate.availability,
        candidate.last_checked_at,
        ttl_seconds=ttl_seconds,
        now=now,
    )
    explanation = candidate.explanation.model_copy(
        update={
            "live_status": presented,
            "last_checked_at": candidate.last_checked_at,
        }
    )
    return candidate.model_copy(update={"availability": presented, "explanation": explanation})
