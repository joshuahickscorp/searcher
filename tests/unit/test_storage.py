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
