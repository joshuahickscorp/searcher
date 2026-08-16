"""Campaign runner that discovers live listings from admitted sources."""

from __future__ import annotations

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.models import TransitionContext
from searcher.campaigns.states import is_terminal
from searcher.contracts.enums import CampaignState, QueryStatus, QueryType
from searcher.contracts.models import IntentBudget, PrivacySettings, QueryVariant, SearchIntent
from searcher.core.budgets import Budget
from searcher.core.errors import BudgetExceeded, CancelledError
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.receipts.types import SearchExhaustionReceipt
from searcher.sources.engine import DiscoveryEngine, SourceRunSummary

LIVE_STEPS: list[CampaignState] = [
    CampaignState.VALIDATING_INPUT,
    CampaignState.INGESTING_REFERENCES,
    CampaignState.CALIBRATING_REFERENCES,
    CampaignState.DECOMPOSING_REFERENCES,
    CampaignState.FORMING_HYPOTHESES,
    CampaignState.PLANNING_QUERIES,
    CampaignState.PLANNING_SOURCES,
    CampaignState.DISCOVERING,
    CampaignState.ACQUIRING,
    CampaignState.NORMALIZING,
    CampaignState.DEDUPLICATING,
    CampaignState.BROAD_RETRIEVAL,
    CampaignState.GAP_ANALYSIS,
    CampaignState.COMPLETE,
]


class LiveDiscoveryRunner:
    def __init__(self, controller: CampaignController) -> None:
        self.controller = controller
        self.last_summary: SourceRunSummary | None = None

    def create(
        self,
        query_text: str,
        *,
        language: str = "en",
        extra_queries: list[tuple[str, str]] | None = None,
        wall_seconds: int = 180,
        page_limit: int = 40,
        source_limit: int = 8,
        byte_limit: int = 8_000_000,
    ) -> SearchIntent:
        search_id = new_id()
        intent = SearchIntent(
            search_id=search_id,
            created_at=utc_now(),
            text=query_text,
            tags=["live-discovery"],
            budget=IntentBudget(
                wall_seconds=wall_seconds,
                source_limit=source_limit,
                page_limit=page_limit,
                browser_page_limit=0,
                image_limit=20,
                model_call_limit=0,
                byte_limit=byte_limit,
            ),
            privacy=PrivacySettings(),
        )
        budget = Budget(
            wall_seconds=wall_seconds,
            source_limit=source_limit,
            page_limit=page_limit,
            browser_page_limit=0,
            image_limit=20,
            model_call_limit=0,
            byte_limit=byte_limit,
            retry_limit=4,
            storage_limit=50_000_000,
        )
        self.controller.create(intent, budget=budget)
        variants = [(language, query_text)] + list(extra_queries or [])
        ids: list[str] = []
        for lang, text in variants:
            query = QueryVariant(
                query_id=new_id(),
                hypothesis_id="live",
                round=1,
                language=lang,
                query_text=text,
                query_type=QueryType.EXACT_NAME if lang == language else QueryType.TRANSLATED,
                status=QueryStatus.QUEUED,
                expected_gain=0.5,
            )
            self.controller.repos.upsert_query(search_id, query)
            ids.append(query.query_id)
        self.controller.set_runtime(search_id, query_ids=ids, live_discovery=True)
        return intent

    def run(
        self, search_id: str, *, source_names: list[str] | None = None
    ) -> SourceRunSummary | None:  # noqa: E501
        engine = DiscoveryEngine(self.controller)
        try:
            runtime = self.controller.repos.get_runtime(search_id)
            completed = {str(s) for s in (runtime.get("completed_steps") or [])}
            for state in LIVE_STEPS:
                campaign = self.controller.get(search_id)
                if is_terminal(campaign.state) and campaign.state is not state:
                    return self.last_summary
                if state.value in completed:
                    continue
                self.controller.cancellation.raise_if_cancelled(search_id)
                if campaign.state is not state:
                    ctx = self._context(search_id, state)
                    self.controller.transition(search_id, state, context=ctx)
                if state is CampaignState.DISCOVERING:
                    from searcher.index.consult import consult_and_surface, remember_campaign

                    consult_and_surface(self.controller, search_id)
                    runtime = self.controller.repos.get_runtime(search_id)
                    if not runtime.get("index_skip_source_work"):
                        from searcher.sources.broker import DEFAULT_ORDER
                        from searcher.sources.families import (
                            names_for_scopes,
                            normalize_source_scopes,
                        )

                        queries = self.controller.repos.list_queries(search_id)
                        scopes = normalize_source_scopes(runtime.get("source_scopes"))
                        preferred = tuple(source_names) if source_names is not None else None
                        scoped = list(
                            names_for_scopes(scopes, preferred, default_order=DEFAULT_ORDER)
                        )
                        self.last_summary = engine.run(
                            search_id,
                            queries,
                            source_names=scoped,
                            families=frozenset(scopes),
                        )
                    remember_campaign(self.controller, search_id)
                    self.controller.persist_usage(search_id)
                if state is CampaignState.COMPLETE:
                    self._complete(search_id)
                self.controller.checkpoint(search_id, state.value)
                self.controller.mark_step(search_id, state.value)
            return self.last_summary
        except CancelledError:
            raise
        except BudgetExceeded:
            campaign = self.controller.get(search_id)
            if not is_terminal(campaign.state):
                ctx = self.controller.context_from_disk(search_id)
                ctx.reason = "budget exhausted"
                self.controller.transition(search_id, CampaignState.PARTIAL, context=ctx)
            return self.last_summary
        finally:
            engine.close()

    def resume(
        self, search_id: str, *, source_names: list[str] | None = None
    ) -> SourceRunSummary | None:  # noqa: E501
        return self.run(search_id, source_names=source_names)

    def _context(self, search_id: str, target: CampaignState) -> TransitionContext:
        ctx = self.controller.context_from_disk(search_id)
        if target is CampaignState.COMPLETE:
            runtime = self.controller.repos.get_runtime(search_id)
            receipt = runtime.get("exhaustion_receipt")
            if not receipt:
                sealed = SearchExhaustionReceipt(
                    search_id=search_id,
                    reason="discovery sources exhausted or budget reached",
                    saturation=False,
                    queries_exhausted=len(self.controller.repos.list_queries(search_id)),
                    sources_covered=len(self.controller.repos.list_source_runs(search_id)),
                ).seal()
                self.controller.store_receipt(sealed)
                receipt = sealed.receipt_id
                self.controller.set_runtime(search_id, exhaustion_receipt=receipt)
            ctx.exhaustion_receipt = str(receipt)
            ctx.reason = "discovery complete"
        return ctx

    def _complete(self, search_id: str) -> None:
        for query in self.controller.repos.list_queries(search_id):
            if query.status in {QueryStatus.QUEUED, QueryStatus.RUNNING}:
                self.controller.repos.upsert_query(
                    search_id, query.model_copy(update={"status": QueryStatus.EXHAUSTED})
                )
