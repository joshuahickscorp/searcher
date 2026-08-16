"""Full offline campaign through every orchestrator stage."""

from __future__ import annotations

import os
from typing import Any

import pytest
from tests.support.offline_shop import (
    install_offline_adapter,
    remove_offline_adapter,
    start_shop,
    tiny_png,
)

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.events import list_events
from searcher.campaigns.orchestrator import CampaignOrchestrator
from searcher.contracts.enums import CampaignState, PublicEventName
from searcher.receipts.types import typed_from_payload
from searcher.workers.api_campaign import create_api_campaign

REQUIRED_STATES = [
    CampaignState.VALIDATING_INPUT.value,
    CampaignState.INGESTING_REFERENCES.value,
    CampaignState.CALIBRATING_REFERENCES.value,
    CampaignState.DECOMPOSING_REFERENCES.value,
    CampaignState.FORMING_HYPOTHESES.value,
    CampaignState.PLANNING_QUERIES.value,
    CampaignState.PLANNING_SOURCES.value,
    CampaignState.DISCOVERING.value,
    CampaignState.ACQUIRING.value,
    CampaignState.NORMALIZING.value,
    CampaignState.DEDUPLICATING.value,
    CampaignState.BROAD_RETRIEVAL.value,
    CampaignState.FINE_MATCHING.value,
    CampaignState.AUTHENTICITY_REVIEW.value,
    CampaignState.LIVE_CHECKING.value,
    CampaignState.RANKING.value,
    CampaignState.PUBLISHING.value,
    CampaignState.GAP_ANALYSIS.value,
]


@pytest.fixture
def shop(monkeypatch: Any) -> Any:
    previous = os.environ.get("SEARCHER_ALLOW_LOOPBACK")
    os.environ["SEARCHER_ALLOW_LOOPBACK"] = "1"
    httpd, base = start_shop()
    install_offline_adapter(base)
    try:
        yield base
    finally:
        remove_offline_adapter()
        httpd.shutdown()
        if previous is None:
            os.environ.pop("SEARCHER_ALLOW_LOOPBACK", None)
        else:
            os.environ["SEARCHER_ALLOW_LOOPBACK"] = previous


def _create(controller: CampaignController) -> str:
    return create_api_campaign(
        controller,
        uploads=[(tiny_png(), "ref.png")],
        text="Archive Alpha Trainer 2007",
        tags=["archive", "trainer", "2007"],
        client_search_id=None,
        settings=controller.settings,
    )


@pytest.mark.timeout(120)
def test_offline_orchestrator_walks_every_stage(controller: CampaignController, shop: str) -> None:
    del shop
    search_id = _create(controller)
    CampaignOrchestrator(controller, source_names=["offline_shop"], max_rounds=2, max_work=12).run(
        search_id
    )
    campaign = controller.get(search_id)
    assert campaign.state in {
        CampaignState.COMPLETE,
        CampaignState.PARTIAL,
        CampaignState.BLOCKED,
    }
    assert campaign.terminal_status is not None
    assert campaign.terminal_status.value != CampaignState.FAILED.value
    runtime = controller.repos.get_runtime(search_id)
    completed = [str(item) for item in (runtime.get("completed_steps") or [])]
    for state in REQUIRED_STATES:
        assert state in completed, f"missing stage {state} in {completed}"
    events = list_events(controller.repos, search_id)
    names = {item.event_name for item in events}
    assert PublicEventName.SEARCH_STATE.value in names
    assert PublicEventName.SEARCH_PROGRESS.value in names
    assert PublicEventName.SEARCH_COMPLETE.value in names
    receipts = controller.repos.list_receipts(search_id)
    types = {row["receipt_type"] for row in receipts}
    assert "SearchExhaustionReceipt" in types
    assert "CampaignTerminalReceipt" in types
    assert "CandidateNormalizationReceipt" in types
    assert "DeduplicationReceipt" in types
    exhaustion = next(
        typed_from_payload(row)
        for row in receipts
        if row["receipt_type"] == "SearchExhaustionReceipt"
    )
    assert exhaustion.reason
    usage = controller.usage(search_id)
    snap = usage.snapshot()
    assert usage.never_exceeds_ceiling()
    assert snap["sealed"]["digest"]
    candidates = controller.repos.list_candidates(search_id)
    assert candidates
    decisions = controller.repos.list_decisions(search_id)
    assert decisions
    replica = [
        item
        for item in candidates
        if item.title and item.title.value and "replica" in str(item.title.value).lower()
    ]
    if replica:
        replica_decisions = [
            item for item in decisions if item.candidate_id == replica[0].candidate_id
        ]
        assert replica_decisions
        assert replica_decisions[0].decision.public.value == "hidden"
        assert "SELF_DECLARED_REPLICA" in replica_decisions[0].hard_vetoes
        public_ids = {
            str(row["candidate_id"])
            for row in controller.repos.list_results(search_id)
            if str(row["public_bucket"]) in {"real", "possibly_real"}
        }
        assert replica[0].candidate_id not in public_ids
    queries = controller.repos.list_queries(search_id)
    languages = {item.language for item in queries}
    assert "en" in languages
    assert campaign.search_exhaustion_receipt


def test_orchestrator_degrades_without_sources(controller: CampaignController) -> None:
    search_id = _create(controller)
    CampaignOrchestrator(controller, source_names=["no_such_adapter"], max_rounds=1).run(search_id)
    campaign = controller.get(search_id)
    assert campaign.state in {CampaignState.BLOCKED, CampaignState.PARTIAL, CampaignState.COMPLETE}
    assert campaign.terminal_status is not None
    assert campaign.terminal_status.value != "FAILED"
    assert campaign.terminal_reason
    if campaign.state is CampaignState.COMPLETE:
        assert campaign.search_exhaustion_receipt
