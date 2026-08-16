"""§3.8 SourceOutcome taxonomy used at every acquisition layer."""

from __future__ import annotations

from searcher.contracts.enums import (
    BLOCKED_SOURCE_OUTCOMES,
    FAILED_SOURCE_OUTCOMES,
    SourceOutcome,
)
from searcher.contracts.routing import as_searched_no_match, assert_outcome_honest
from searcher.core.errors import InvariantViolation
from searcher.sources.challenge import looks_like_challenge as body_looks_like_challenge

__all__ = [
    "BLOCKED_SOURCE_OUTCOMES",
    "FAILED_SOURCE_OUTCOMES",
    "SourceOutcome",
    "as_searched_no_match",
    "assert_outcome_honest",
    "classify_http",
    "is_block",
    "is_failure",
    "is_success",
    "record_outcome",
]


def is_block(outcome: SourceOutcome) -> bool:
    return outcome in BLOCKED_SOURCE_OUTCOMES


def is_failure(outcome: SourceOutcome) -> bool:
    return outcome in FAILED_SOURCE_OUTCOMES


def is_success(outcome: SourceOutcome) -> bool:
    return outcome in {
        SourceOutcome.SEARCHED_NO_MATCH,
        SourceOutcome.SEARCHED_MATCHES_FOUND,
    }


def record_outcome(claimed: SourceOutcome, actual: SourceOutcome) -> SourceOutcome:
    """Refuse to collapse a block/failure into SEARCHED_NO_MATCH."""
    return assert_outcome_honest(claimed, actual)


def classify_http(
    status: int | None,
    *,
    body: bytes | str | None = None,
    challenge: bool = False,
) -> SourceOutcome:
    """Map an HTTP result to a §3.8 outcome. Never returns SEARCHED_NO_MATCH."""
    if challenge:
        return SourceOutcome.BLOCKED_BY_ACCESS
    if status is None:
        return SourceOutcome.NETWORK_FAILED
    if status == 401:
        return SourceOutcome.AUTH_REQUIRED
    if status == 403:
        return SourceOutcome.BLOCKED_BY_ACCESS
    if status == 429:
        return SourceOutcome.RATE_LIMITED
    if status == 404 or status == 410:
        # Gone is a measurable empty-for-this-URL, not a source-wide no-match.
        return SourceOutcome.SEARCHED_NO_MATCH
    if status == 408 or status == 504:
        return SourceOutcome.NETWORK_FAILED
    if 500 <= status <= 599:
        return SourceOutcome.SOURCE_UNAVAILABLE
    if status == 200 or status == 304:
        text = _as_text(body)
        if _looks_like_challenge(text):
            return SourceOutcome.BLOCKED_BY_ACCESS
        return SourceOutcome.SEARCHED_MATCHES_FOUND
    if 300 <= status < 400:
        return SourceOutcome.NETWORK_FAILED
    return SourceOutcome.UNMEASURABLE


def _as_text(body: bytes | str | None) -> str:
    if body is None:
        return ""
    if isinstance(body, bytes):
        return body[:8000].decode("utf-8", errors="replace")
    return body[:8000]


def _looks_like_challenge(text: str) -> bool:
    return body_looks_like_challenge(text)


def refuse_no_match_collapse(outcome: SourceOutcome) -> SourceOutcome:
    if outcome is SourceOutcome.SEARCHED_NO_MATCH:
        return outcome
    if is_block(outcome) or is_failure(outcome):
        raise InvariantViolation(
            f"blocked or failed source cannot be recorded as SEARCHED_NO_MATCH ({outcome})"
        )
    return outcome
