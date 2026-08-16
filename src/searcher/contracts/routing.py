"""Routing and source-outcome guards used by campaigns and property tests."""

from __future__ import annotations

from searcher.contracts.enums import (
    BLOCKED_SOURCE_OUTCOMES,
    FAILED_SOURCE_OUTCOMES,
    Availability,
    BucketInternal,
    BucketPublic,
    SourceOutcome,
)
from searcher.core.errors import InvariantViolation
from searcher.core.policy import GateView, route_public_bucket


def is_blocked_outcome(outcome: SourceOutcome) -> bool:
    return outcome in BLOCKED_SOURCE_OUTCOMES


def record_source_outcome(outcome: SourceOutcome) -> SourceOutcome:
    """Identity. The coercion guard below is what property tests mutate."""
    return outcome


def as_searched_no_match(outcome: SourceOutcome) -> SourceOutcome:
    """GUARD: a blocked (or failed/unmeasurable) source cannot be no-match."""
    if outcome in BLOCKED_SOURCE_OUTCOMES or outcome in FAILED_SOURCE_OUTCOMES:
        raise InvariantViolation(
            f"blocked or failed source cannot be recorded as SEARCHED_NO_MATCH ({outcome})"
        )
    if outcome in {SourceOutcome.NOT_ATTEMPTED, SourceOutcome.SEARCHED_MATCHES_FOUND}:
        raise InvariantViolation(f"{outcome} cannot be recorded as SEARCHED_NO_MATCH")
    return SourceOutcome.SEARCHED_NO_MATCH


def assert_outcome_honest(claimed: SourceOutcome, actual: SourceOutcome) -> SourceOutcome:
    if claimed == SourceOutcome.SEARCHED_NO_MATCH and actual != SourceOutcome.SEARCHED_NO_MATCH:
        return as_searched_no_match(actual)
    return claimed


def public_bucket_from_view(view: GateView) -> BucketPublic:
    return BucketPublic(route_public_bucket(view))


def internal_bucket_from_public(
    public: BucketPublic,
    *,
    hard_vetoes: list[str],
    quarantined: bool = False,
) -> BucketInternal:
    if hard_vetoes:
        return BucketInternal.QUARANTINED if quarantined else BucketInternal.REJECTED
    if public == BucketPublic.REAL:
        return BucketInternal.REAL
    if public == BucketPublic.POSSIBLY_REAL:
        return BucketInternal.POSSIBLY_REAL
    return BucketInternal.REJECTED


def require_live_for_real(
    *,
    availability: Availability,
    live_checked: bool,
    intended: BucketPublic,
) -> BucketPublic:
    """GUARD: a dead listing cannot become Real."""
    if intended == BucketPublic.REAL and (availability != Availability.LIVE or not live_checked):
        return BucketPublic.HIDDEN
    return intended
