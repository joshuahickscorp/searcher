"""Storage round-trips and optimistic concurrency."""

from __future__ import annotations

import pytest
from tests.conftest import make_intent

from searcher.contracts.enums import Availability, CampaignState, FactClass, FactOrigin
from searcher.contracts.models import ListingCandidate
from searcher.contracts.primitives import ClassifiedFact
from searcher.core.budgets import Budget
from searcher.core.errors import StaleStateVersion
from searcher.core.ids import new_id
from searcher.core.time import parse_utc


def test_campaign_roundtrip(controller: object) -> None:
    intent = make_intent()
    created = controller.create(intent, budget=Budget.fixture_default())  # type: ignore[attr-defined]
    loaded = controller.get(intent.search_id)  # type: ignore[attr-defined]
    assert loaded.search_id == created.search_id
    assert loaded.state is CampaignState.CREATED
    assert loaded.state_version == 0


def test_stale_write_rejected(controller: object) -> None:
    intent = make_intent()
    controller.create(intent, budget=Budget.fixture_default())  # type: ignore[attr-defined]
    campaign = controller.get(intent.search_id)  # type: ignore[attr-defined]
    campaign.state = CampaignState.VALIDATING_INPUT
    controller.repos.update_campaign_blob(campaign, expected_version=0)  # type: ignore[attr-defined]
    with pytest.raises(StaleStateVersion):
        controller.repos.update_campaign_blob(campaign, expected_version=0)  # type: ignore[attr-defined]


def test_concurrent_readers_never_see_null_intent_json(controller: object) -> None:
    """A second thread must not reset a live SELECT; that sent campaigns to FAILED."""
    import threading

    intent = make_intent()
    controller.create(intent, budget=Budget.fixture_default())  # type: ignore[attr-defined]
    search_id = intent.search_id
    stop = threading.Event()
    problems: list[str] = []

    def _read() -> None:
        while not stop.is_set():
            try:
                row = controller.db.execute(  # type: ignore[attr-defined]
                    "SELECT intent_json, runtime_json FROM campaigns WHERE search_id = ?",
                    (search_id,),
                ).fetchone()
                if row is None:
                    problems.append("missing row")
                    continue
                if row["intent_json"] is None or row["runtime_json"] is None:
                    problems.append("null json column")
                    stop.set()
                    return
                loaded = controller.get(search_id)  # type: ignore[attr-defined]
                assert loaded.search_id == search_id
            except Exception as exc:  # noqa: BLE001 — the race is the thing under test
                problems.append(f"{type(exc).__name__}: {exc}")
                if len(problems) >= 8:
                    stop.set()
                    return

    def _write() -> None:
        n = 0
        while not stop.is_set():
            n += 1
            controller.set_runtime(search_id, tick=n)  # type: ignore[attr-defined]
            controller.emit(  # type: ignore[attr-defined]
                search_id,
                "search.progress",
                payload={"stage": "tick", "detail": str(n)},
                actor="race",
            )

    readers = [threading.Thread(target=_read) for _ in range(4)]
    writers = [threading.Thread(target=_write) for _ in range(2)]
    for thread in readers + writers:
        thread.start()
    stop.wait(timeout=1.0)
    stop.set()
    for thread in readers + writers:
        thread.join(timeout=2.0)
    assert not problems, problems


def test_candidate_roundtrip(controller: object) -> None:
    intent = make_intent()
    controller.create(intent, budget=Budget.fixture_default())  # type: ignore[attr-defined]
    now = parse_utc("2007-06-15T12:00:00+00:00")
    candidate = ListingCandidate(
        candidate_id=new_id(),
        canonical_url="https://fixture.local/x",
        source_adapter="fixture",
        title=ClassifiedFact(
            value="x", fact_class=FactClass.REPORTED_BY_SELLER, origin=FactOrigin.SELLER
        ),
        availability=Availability.LIVE,
        first_seen_at=now,
        last_checked_at=now,
    )
    controller.repos.upsert_candidate(intent.search_id, candidate)  # type: ignore[attr-defined]
    loaded = controller.repos.list_candidates(intent.search_id)  # type: ignore[attr-defined]
    assert loaded[0].candidate_id == candidate.candidate_id
    assert loaded[0].title is not None
    assert loaded[0].title.fact_class is FactClass.REPORTED_BY_SELLER
