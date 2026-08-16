"""Honest SourceOutcome classification."""

from __future__ import annotations

import pytest

from searcher.contracts.enums import SourceOutcome
from searcher.contracts.routing import as_searched_no_match
from searcher.core.errors import InvariantViolation
from searcher.sources.live_check import classify_liveness
from searcher.sources.statuses import classify_http


def test_403_is_blocked_not_empty() -> None:
    assert classify_http(403) is SourceOutcome.BLOCKED_BY_ACCESS


def test_429_is_rate_limited() -> None:
    assert classify_http(429) is SourceOutcome.RATE_LIMITED


def test_401_is_auth_required() -> None:
    assert classify_http(401) is SourceOutcome.AUTH_REQUIRED


def test_challenge_page_is_blocked() -> None:
    assert classify_http(200, body=b"Just a moment...") is SourceOutcome.BLOCKED_BY_ACCESS


def test_blocked_cannot_become_no_match() -> None:
    with pytest.raises(InvariantViolation):
        as_searched_no_match(SourceOutcome.BLOCKED_BY_ACCESS)


def test_liveness_403_is_blocked_not_sold() -> None:
    status = classify_liveness(
        http_status=403,
        body="",
        outcome=SourceOutcome.BLOCKED_BY_ACCESS,
    )
    assert status.note == "blocked, not sold"
    assert status.availability.value == "UNKNOWN"


def test_liveness_404_is_removed() -> None:
    status = classify_liveness(http_status=404, body="", outcome=SourceOutcome.SEARCHED_NO_MATCH)
    assert status.availability.value == "REMOVED"


def test_liveness_sold_marker() -> None:
    status = classify_liveness(
        http_status=200,
        body="This listing has ended. 売り切れ",
        outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
    )
    assert status.availability.value == "SOLD"
