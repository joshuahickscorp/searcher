"""A source is only reach if it can answer.

searx is admitted and enabled, but its manifest points at localhost until
SEARCHER_SEARX_URL is set, and this project's own SSRF gate refuses localhost.
Counting it as reach overstated coverage on every campaign and produced a
SOURCE_UNAVAILABLE that reads as "the source is down" rather than "we pointed
it at loopback".
"""

from __future__ import annotations

import pytest

from searcher.contracts.enums import SourceOutcome
from searcher.sources.adapters import ADAPTER_REGISTRY
from searcher.workers.api_campaign import uncredentialed_source_names


def test_searx_is_not_reach_without_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEARCHER_SEARX_URL", raising=False)
    assert "searx" not in uncredentialed_source_names()


def test_searx_becomes_reach_once_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCHER_SEARX_URL", "https://searx.example.org")
    assert "searx" in uncredentialed_source_names()


def test_no_advertised_source_reports_itself_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SEARCHER_SEARX_URL", raising=False)
    for name in uncredentialed_source_names():
        health = ADAPTER_REGISTRY[name]().health_check()
        outcome = getattr(health, "last_outcome", None) or getattr(health, "outcome", None)
        assert outcome is not SourceOutcome.SOURCE_UNAVAILABLE, (
            f"{name} is advertised as reach while reporting itself unavailable"
        )
