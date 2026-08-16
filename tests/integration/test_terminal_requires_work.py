"""A campaign that did no work is BLOCKED, never COMPLETE."""

from __future__ import annotations

from tests.conftest import make_budget, make_intent
from tests.support.offline_shop import tiny_png

from searcher.campaigns.orchestrator import CampaignOrchestrator
from searcher.contracts.enums import CampaignState, QueryType
from searcher.contracts.models import QueryVariant
from searcher.core.ids import new_id
from searcher.workers.api_campaign import create_api_campaign


def _query(search_id: str) -> QueryVariant:
    del search_id
    return QueryVariant(
        query_id=new_id(),
        hypothesis_id=new_id(),
        round=1,
        language="en",
        query_text="Archive Alpha Trainer",
        query_type=QueryType.EXACT_NAME,
    )


def test_choose_terminal_without_work_is_blocked(controller: object) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())  # type: ignore[attr-defined]
    orch = CampaignOrchestrator(controller)  # type: ignore[arg-type]
    state, reason, saturation = orch._choose_terminal(intent.search_id, forced=None)
    assert state is CampaignState.BLOCKED
    assert state is not CampaignState.COMPLETE
    assert state.value != CampaignState.COMPLETE.value
    assert "coverage exhausted" not in reason
    lowered = reason.lower()
    assert any(
        token in lowered
        for token in ("query", "source work", "fetched", "nothing", "planned", "compiled")
    )
    assert saturation is False


def test_zero_fetch_run_is_blocked_never_complete(controller: object) -> None:
    search_id = create_api_campaign(
        controller,  # type: ignore[arg-type]
        uploads=[(tiny_png(), "ref.png")],
        text="Archive Alpha Trainer 2007",
        tags=["archive"],
        client_search_id=None,
        settings=controller.settings,  # type: ignore[attr-defined]
    )
    CampaignOrchestrator(controller, source_names=["no_such_adapter"], max_rounds=1).run(  # type: ignore[arg-type]
        search_id
    )
    campaign = controller.get(search_id)  # type: ignore[attr-defined]
    assert campaign.terminal_status is not None
    assert campaign.terminal_status.value == CampaignState.BLOCKED.value
    assert campaign.terminal_status.value != CampaignState.COMPLETE.value
    reason = (campaign.terminal_reason or "").lower()
    assert reason
    assert "coverage exhausted" not in reason
    assert any(
        token in reason
        for token in (
            "query",
            "source",
            "fetch",
            "nothing",
            "planned",
            "compiled",
            "discovery",
            "admitted",
        )
    )


def test_complete_requires_searched_coverage(controller: object) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())  # type: ignore[attr-defined]
    controller.repos.upsert_query(intent.search_id, _query(intent.search_id))  # type: ignore[attr-defined]
    controller.set_runtime(  # type: ignore[attr-defined]
        intent.search_id,
        coverage={
            "sources_completed": [
                {
                    "id": "kind",
                    "name": "kind",
                    "status": "SEARCHED_MATCHES_FOUND",
                    "detail": "",
                }
            ],
            "sources_blocked": [],
            "pages_fetched": 2,
            "candidates_normalized": 0,
            "candidates_hidden": 0,
        },
    )
    orch = CampaignOrchestrator(controller)  # type: ignore[arg-type]
    state, reason, saturation = orch._choose_terminal(intent.search_id, forced=None)
    assert state is CampaignState.COMPLETE
    assert reason == "coverage exhausted"
    assert saturation is False
