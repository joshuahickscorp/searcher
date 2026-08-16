"""Searcher-owned JobScraperAdapter. Does not import donor scraper.*."""

from __future__ import annotations

from dataclasses import dataclass

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import SourceOutcome
from searcher.contracts.models import FetchResult, SourcePlan
from searcher.sources.engine import DiscoveryEngine
from searcher.sources.frontier import Frontier


@dataclass
class SourceRunRef:
    run_id: str
    search_id: str
    source_id: str


@dataclass
class DiscoveryBatch:
    pages: list[str]
    cursor: str | None = None


@dataclass
class SourceRunState:
    run_id: str
    cursor: str | None
    outcome: str


class InProcessJobScraperAdapter:
    def __init__(self, controller: CampaignController) -> None:
        self.controller = controller
        self.engine = DiscoveryEngine(controller)

    async def start_source_run(self, plan: SourcePlan) -> SourceRunRef:
        search_id = str(plan.budget.get("search_id") or plan.source_plan_id)
        self.controller.repos.upsert_source_run(
            search_id,
            plan.source_plan_id,
            plan.source_adapter,
            cursor=None,
            last_outcome=SourceOutcome.NOT_ATTEMPTED.value,
            payload=plan.model_dump(mode="json"),
        )
        return SourceRunRef(plan.source_plan_id, search_id, plan.source_adapter)

    async def next_discovery_batch(self, run: SourceRunRef) -> DiscoveryBatch:
        frontier = Frontier(self.controller.repos, run.run_id)
        frontier.recover()
        items = frontier.pop(5)
        return DiscoveryBatch(pages=[item.url for item in items])

    async def fetch_candidates(self, urls: list[str]) -> list[FetchResult]:
        del urls
        return []

    async def resume(self, run: SourceRunRef) -> SourceRunState:
        rows = self.controller.repos.list_source_runs(run.search_id)
        for row in rows:
            if str(row["source_run_id"]) == run.run_id:
                return SourceRunState(
                    run.run_id,
                    row.get("cursor_json"),
                    str(row.get("last_outcome") or ""),
                )
        return SourceRunState(run.run_id, None, SourceOutcome.NOT_ATTEMPTED.value)

    async def cancel(self, run: SourceRunRef) -> None:
        self.controller.cancellation.request(run.search_id)


class NullJobScraperAdapter:
    async def start_source_run(self, plan: SourcePlan) -> SourceRunRef:
        return SourceRunRef(plan.source_plan_id, "", plan.source_adapter)

    async def next_discovery_batch(self, run: SourceRunRef) -> DiscoveryBatch:
        del run
        return DiscoveryBatch(pages=[])

    async def fetch_candidates(self, urls: list[str]) -> list[FetchResult]:
        del urls
        return []

    async def resume(self, run: SourceRunRef) -> SourceRunState:
        return SourceRunState(run.run_id, None, SourceOutcome.NOT_ATTEMPTED.value)

    async def cancel(self, run: SourceRunRef) -> None:
        return None
