"""Cancellation mid-pipeline: bounded cleanup, no orphan browsers."""

from __future__ import annotations

import threading
from typing import Any

from tests.support.offline_shop import tiny_png

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.orchestrator import CampaignOrchestrator
from searcher.contracts.enums import CampaignState
from searcher.sources.browser import chromium_pids
from searcher.workers.api_campaign import create_api_campaign


def test_cancel_mid_pipeline_cleans_up(controller: CampaignController, monkeypatch: Any) -> None:
    before = chromium_pids()
    started = threading.Event()
    release = threading.Event()

    def hold(self: CampaignOrchestrator, search_id: str) -> None:
        del self
        started.set()
        release.wait(timeout=15)
        controller.cancellation.raise_if_cancelled(search_id)

    monkeypatch.setattr(CampaignOrchestrator, "_discover", hold)
    search_id = create_api_campaign(
        controller,
        uploads=[(tiny_png(), "ref.png")],
        text="Archive trainer",
        tags=["trainer"],
        client_search_id=None,
        settings=controller.settings,
    )
    thread = threading.Thread(
        target=CampaignOrchestrator(controller, source_names=["offline_shop"]).run,
        args=(search_id,),
        daemon=True,
    )
    thread.start()
    assert started.wait(timeout=10)
    cancelled = controller.cancel(search_id)
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    campaign = controller.get(search_id)
    assert campaign.state is CampaignState.CANCELLED
    assert cancelled.state is CampaignState.CANCELLED
    after = chromium_pids()
    assert not (after - before), f"orphaned browsers: {after - before}"
