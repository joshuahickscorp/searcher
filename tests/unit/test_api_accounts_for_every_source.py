"""The API path names every known source, including those it does not search.

The nine-name pre-filter meant the broker never saw the other fifteen, so
they could not appear as skips. This file fails on that pre-filter: it
asserts the API hands all 24 names to the broker, that searx is reported
SOURCE_UNAVAILABLE and not planned, and that the planned set equals the
answerable set uncredentialed_source_names() already defined.
"""

from __future__ import annotations

import pytest
from tests.conftest import make_intent

from searcher.contracts.enums import QueryType, SourceOutcome
from searcher.contracts.models import QueryVariant
from searcher.core.budgets import Budget
from searcher.core.ids import new_id
from searcher.sources.broker import DEFAULT_ORDER, SourceBroker
from searcher.workers.api_campaign import run_api_campaign, uncredentialed_source_names


def _query(language: str = "en") -> QueryVariant:
    return QueryVariant(
        query_id=new_id(),
        hypothesis_id="h",
        round=1,
        language=language,
        query_text="dior homme trainer",
        query_type=QueryType.EXACT_NAME,
        expected_gain=0.5,
    )


def _api_plan(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], dict[str, str]]:
    monkeypatch.delenv("SEARCHER_SEARX_URL", raising=False)
    from searcher.workers.api_campaign import api_source_names

    names = api_source_names()
    broker = SourceBroker(names=tuple(names))
    plans = broker.plan([_query()], skip_unanswerable=True)
    planned = [plan.source_adapter for plan in plans]
    return planned, dict(broker.coverage.per_source)


def test_api_source_names_are_every_known_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEARCHER_SEARX_URL", raising=False)
    from searcher.workers.api_campaign import api_source_names

    names = api_source_names()
    assert names == list(DEFAULT_ORDER)
    assert len(names) == 24
    # The pre-filter this file exists to catch: nine answerable names is not
    # an account of the known set.
    assert names != uncredentialed_source_names()
    assert len(uncredentialed_source_names()) == 9


def test_searx_is_reported_but_not_searched(monkeypatch: pytest.MonkeyPatch) -> None:
    planned, skipped = _api_plan(monkeypatch)
    assert "searx" not in planned
    assert skipped.get("searx") == SourceOutcome.SOURCE_UNAVAILABLE.value
    assert skipped.get("ebay") == SourceOutcome.AUTH_REQUIRED.value
    assert skipped.get("etsy") == SourceOutcome.AUTH_REQUIRED.value
    assert skipped.get("ssense") == SourceOutcome.BLOCKED_BY_POLICY.value
    assert skipped.get("taobao") == SourceOutcome.BLOCKED_BY_POLICY.value
    assert skipped.get("yupoo") == SourceOutcome.BLOCKED_BY_POLICY.value


def test_known_source_count_is_twenty_four(monkeypatch: pytest.MonkeyPatch) -> None:
    planned, skipped = _api_plan(monkeypatch)
    accounted = set(planned) | set(skipped)
    assert len(accounted) == 24
    assert accounted == set(DEFAULT_ORDER)
    assert len(planned) == 9
    assert len(skipped) == 15


def test_planned_set_is_the_uncredentialed_answerable_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove the fetched set, do not hard-code it."""
    planned, skipped = _api_plan(monkeypatch)
    answerable = uncredentialed_source_names()
    assert set(planned) == set(answerable)
    assert "searx" not in answerable
    assert "searx" in skipped


def test_api_hands_every_known_source_to_the_orchestrator(
    controller: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, list[str]] = {}

    class _FakeOrchestrator:
        def __init__(
            self,
            _controller: object,
            *,
            source_names: list[str] | None = None,
            **_kwargs: object,
        ) -> None:
            captured["names"] = list(source_names or [])

        def run(self, search_id: str) -> None:
            del search_id

    monkeypatch.setattr("searcher.workers.api_campaign.FastOrchestrator", _FakeOrchestrator)
    monkeypatch.setattr("searcher.workers.api_campaign._should_run_live", lambda _settings: True)
    monkeypatch.setattr(
        "searcher.workers.api_campaign.account_for_every_known_source",
        lambda *_args, **_kwargs: None,
        raising=False,
    )
    intent = make_intent()
    controller.create(intent, budget=Budget.fixture_default())  # type: ignore[attr-defined]
    run_api_campaign(controller, intent.search_id)  # type: ignore[arg-type]
    assert captured["names"] == list(DEFAULT_ORDER)
    assert len(captured["names"]) == 24


def test_account_for_every_known_source_fills_the_fifteen(
    controller: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SEARCHER_SEARX_URL", raising=False)
    intent = make_intent()
    controller.create(intent, budget=Budget.fixture_default())  # type: ignore[attr-defined]
    controller.repos.upsert_query(intent.search_id, _query())  # type: ignore[attr-defined]
    # A live run that only named the nine answerable sources.
    controller.set_runtime(  # type: ignore[attr-defined]
        intent.search_id,
        coverage={
            "sources_completed": [
                {"id": name, "name": name, "status": "SEARCHED_NO_MATCH", "detail": ""}
                for name in uncredentialed_source_names()
            ],
            "sources_blocked": [],
            "sources_in_progress": [],
            "pages_fetched": 0,
            "candidates_normalized": 0,
            "candidates_hidden": 0,
        },
    )
    from searcher.workers.api_campaign import account_for_every_known_source

    account_for_every_known_source(controller, intent.search_id)  # type: ignore[arg-type]
    runtime = controller.repos.get_runtime(intent.search_id)  # type: ignore[attr-defined]
    coverage = runtime["coverage"]
    completed = {row["id"] for row in coverage["sources_completed"]}
    blocked = {row["id"]: row["status"] for row in coverage["sources_blocked"]}
    named = completed | set(blocked)
    assert len(named) == 24
    assert named == set(DEFAULT_ORDER)
    assert "searx" not in completed
    assert blocked["searx"] == SourceOutcome.SOURCE_UNAVAILABLE.value
    assert blocked["ebay"] == SourceOutcome.AUTH_REQUIRED.value
    assert blocked["etsy"] == SourceOutcome.AUTH_REQUIRED.value
    for name in ("ssense", "depop", "taobao", "weidian", "yupoo"):
        assert blocked[name] == SourceOutcome.BLOCKED_BY_POLICY.value
