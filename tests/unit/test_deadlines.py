"""Per-request and per-source deadlines fire instead of waiting unbounded."""

from __future__ import annotations

import time

import pytest

from searcher.core.errors import ErrorClass
from searcher.sources.http import FetchError
from searcher.workers.bounded_discovery import DEADLINE_REASON, DeadlineHttpClient


def test_deadline_http_refuses_when_source_budget_is_gone() -> None:
    client = DeadlineHttpClient(timeout=2.0, connect_timeout=1.0)
    try:
        client.set_deadline(time.monotonic() - 0.1)
        with pytest.raises(FetchError, match="deadline") as caught:
            client.get("https://en.wikipedia.org/robots.txt")
        assert caught.value.error_class is ErrorClass.TIMEOUT
        assert DEADLINE_REASON in str(caught.value)
        assert client.deadline_tripped is True
    finally:
        client.close()


def test_deadline_http_caps_remaining_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(time, "sleep", fake_sleep)
    client = DeadlineHttpClient(timeout=2.0, connect_timeout=1.0)
    try:
        limiter = client.limiter_for("https://en.wikipedia.org/wiki/x", 10.0)
        limiter.last_at = time.monotonic()
        client.set_deadline(time.monotonic() + 0.2)
        with pytest.raises(FetchError, match="deadline"):
            client.get("https://en.wikipedia.org/wiki/x", base_delay=10.0, pace=True)
        assert slept == []
        assert client.deadline_tripped is True
    finally:
        client.close()
