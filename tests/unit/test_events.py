"""Append-only event log ordering."""

from __future__ import annotations

from tests.conftest import make_intent

from searcher.campaigns.events import event_chain_ok, list_events
from searcher.contracts.enums import PublicEventName
from searcher.core.budgets import Budget


def test_events_are_chained(controller: object) -> None:
    intent = make_intent()
    controller.create(intent, budget=Budget.fixture_default())  # type: ignore[attr-defined]
    controller.emit(intent.search_id, PublicEventName.SEARCH_PROGRESS.value, payload={"n": 1})  # type: ignore[attr-defined]
    controller.emit(intent.search_id, PublicEventName.SEARCH_COVERAGE.value, payload={"n": 2})  # type: ignore[attr-defined]
    events = list_events(controller.repos, intent.search_id)  # type: ignore[attr-defined]
    assert len(events) >= 3
    assert event_chain_ok(events)
    assert events[0].predecessor is None
    for previous, current in zip(events, events[1:], strict=False):
        assert current.predecessor == previous.event_id
    names = {e.event_name for e in events}
    assert PublicEventName.SEARCH_STATE.value in names
