"""Coverage must publish the page count the page limit actually governs.

A live campaign reported `pages_fetched=60` against `page_limit=40` and an
independent grade recorded it as a budget violation. It is not one. Those are
two different quantities: `pages_fetched` counts every discovery page, while the
page limit caps only HTTP fetches - a browser fetch charges `browser_pages`, a
separate dimension with its own ceiling.

Publishing the total beside a stated limit invites exactly that reading, so the
number the limit governs is published too. A reader should not have to know
which fetch modes charge which dimension to tell whether a limit held.
"""

from __future__ import annotations

from searcher.campaigns.orchestrator import CampaignOrchestrator


class _Repos:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def get_budget_usage(self, search_id: str) -> object:
        return self._payload


class _Controller:
    def __init__(self, payload: object) -> None:
        self.repos = _Repos(payload)


def _charged(payload: object) -> int | None:
    orch = CampaignOrchestrator.__new__(CampaignOrchestrator)
    orch.controller = _Controller(payload)  # type: ignore[assignment]
    return orch._pages_charged("s")


def test_the_charged_page_count_is_read_from_the_ledger() -> None:
    assert _charged({"used": {"pages": 40, "browser_pages": 20}}) == 40


def test_browser_pages_are_not_counted_against_the_page_limit() -> None:
    """The distinction the 60-vs-40 report obscured."""
    charged = _charged({"used": {"pages": 12, "browser_pages": 99}})
    assert charged == 12, "browser fetches charge their own dimension, not the page limit"


def test_a_missing_or_malformed_ledger_reports_nothing_rather_than_zero() -> None:
    """Zero is a measurement. Absence is not, and must not read as one."""
    assert _charged(None) is None
    assert _charged({}) is None
    assert _charged({"used": {}}) is None
    assert _charged({"used": {"pages": "many"}}) is None
    assert _charged("not a dict") is None
