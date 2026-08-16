"""Drive source runs from the Wave 1 campaign controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import (
    FetchMode,
    FrontierState,
    SourceOutcome,
    WorkKind,
)
from searcher.contracts.models import (
    DiscoveryPage,
    ListingCandidate,
    QueryVariant,
    SourceManifest,
    SourcePlan,
)
from searcher.core.errors import BudgetExceeded, CancelledError
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.deduplication.clusters import cluster_candidates
from searcher.receipts.types import SourceAdmissionReceipt, SourceRunReceipt
from searcher.sources.adapters import resolve_adapter
from searcher.sources.adapters.generic_page import listing_links
from searcher.sources.adapters.sitemap import filter_locs, parse_sitemap_locs
from searcher.sources.admission import AdmissionGate
from searcher.sources.broker import Coverage, SourceBroker
from searcher.sources.cache import ResponseCache
from searcher.sources.cancel import RunCancel
from searcher.sources.circuit import CircuitBreaker, CircuitOpen
from searcher.sources.events import SourceEvents
from searcher.sources.fetch_log import FetchLog
from searcher.sources.fetch_modes import Escalator, FetchedDocument
from searcher.sources.frontier import Frontier, compute_priority
from searcher.sources.health import HealthStore
from searcher.sources.http import HonestHttpClient
from searcher.sources.live_check import check_candidate
from searcher.sources.robots import RobotsCache
from searcher.sources.statuses import is_block


@dataclass
class SourceRunSummary:
    search_id: str
    coverage: dict[str, str]
    candidates_before: int
    candidates_after: int
    listings: list[ListingCandidate] = field(default_factory=list)
    blocked: list[dict[str, str]] = field(default_factory=list)


class _HasManifest(Protocol):
    def manifest(self) -> SourceManifest: ...


def _adapter_manifest(adapter: object) -> SourceManifest:
    return cast(_HasManifest, adapter).manifest()


def _kind_for_url(url: str) -> WorkKind:
    if "sitemap" in url:
        return WorkKind.SITEMAP
    if any(
        token in url
        for token in (
            "search",
            "api.php",
            "format=json",
            "/collections/",
            "/shop/",
            "/designers/",
        )
    ):
        return WorkKind.QUERY
    return WorkKind.LISTING


class DiscoveryEngine:
    def __init__(
        self,
        controller: CampaignController,
        *,
        http: HonestHttpClient | None = None,
        batch_size: int = 4,
        max_work: int = 40,
    ) -> None:
        self.controller = controller
        self.http = http or HonestHttpClient()
        self.owns_http = http is None
        self.batch_size = batch_size
        self.max_work = max_work
        self.repos = controller.repos
        self.health = HealthStore(self.repos)
        self.broker = SourceBroker(health=self.health)
        self.robots = RobotsCache(
            user_agent=controller.settings.user_agent,
            ttl_seconds=controller.settings.robots_ttl_seconds,
            repos=self.repos,
        )
        self.admission = AdmissionGate(
            self.robots, self.http, user_agent=controller.settings.user_agent
        )
        self.cache = ResponseCache(self.repos, controller.store)
        self.circuit = CircuitBreaker(self.health)

    def close(self) -> None:
        if self.owns_http:
            self.http.close()

    def run(
        self,
        search_id: str,
        queries: list[QueryVariant],
        *,
        source_names: list[str] | None = None,
        include_disabled: bool = False,
    ) -> SourceRunSummary:
        usage = self.controller.usage(search_id)
        cancel = RunCancel(search_id, self.controller.cancellation)
        events = SourceEvents(self.controller, search_id)
        coverage = Coverage()
        if source_names:
            self.broker.names = tuple(source_names)
        plans = self.broker.plan(queries, usage, include_disabled=include_disabled)
        all_candidates: list[ListingCandidate] = []
        blocked: list[dict[str, str]] = []
        for plan in plans:
            cancel.raise_if_cancelled()
            try:
                usage.consume(sources=1)
            except BudgetExceeded:
                coverage.record(plan.source_adapter, SourceOutcome.UNMEASURABLE)
                break
            summary, found = self._run_plan(search_id, plan, queries, events, cancel)
            coverage.record(plan.source_adapter, SourceOutcome(summary))
            all_candidates.extend(found)
            if is_block(SourceOutcome(summary)):
                blocked.append({"source": plan.source_adapter, "outcome": summary})
        before = len(all_candidates)
        deduped = cluster_candidates(all_candidates)
        for candidate in deduped.representatives:
            self.repos.upsert_candidate(search_id, candidate)
        for cluster in deduped.clusters:
            self.repos.insert_cluster(
                search_id,
                cluster.cluster_id,
                cluster.representative_id,
                {
                    "members": cluster.member_ids,
                    "reason": cluster.reason,
                    "savings": deduped.savings,
                },  # noqa: E501
            )
        runtime = self.controller.repos.get_runtime(search_id)
        runtime["coverage"] = coverage.per_source
        runtime["dedupe_savings"] = deduped.savings
        self.controller.repos.update_runtime(search_id, runtime)
        self.controller.persist_usage(search_id)
        return SourceRunSummary(
            search_id=search_id,
            coverage=coverage.per_source,
            candidates_before=before,
            candidates_after=len(deduped.representatives),
            listings=deduped.representatives,
            blocked=blocked,
        )

    def _run_plan(
        self,
        search_id: str,
        plan: SourcePlan,
        queries: list[QueryVariant],
        events: SourceEvents,
        cancel: RunCancel,
    ) -> tuple[str, list[ListingCandidate]]:
        source_id = plan.source_adapter
        events.source_start(source_id)
        try:
            adapter = resolve_adapter(source_id)
        except KeyError:
            events.blocked(source_id, SourceOutcome.SOURCE_UNAVAILABLE.value, "unknown adapter")
            return SourceOutcome.SOURCE_UNAVAILABLE.value, []
        manifest = _adapter_manifest(adapter)
        run_id = plan.source_plan_id
        self.repos.upsert_source_run(
            search_id,
            run_id,
            source_id,
            cursor=None,
            last_outcome=SourceOutcome.NOT_ATTEMPTED.value,
            payload=plan.model_dump(mode="json"),
        )
        frontier = Frontier(self.repos, run_id)
        frontier.recover()
        log = FetchLog(self.repos, search_id)
        escalator = Escalator(
            self.http,
            self.admission,
            self.cache,
            fetch_log=log,
            usage=self.controller.usage(search_id),
            cancel=cancel,
        )
        if hasattr(adapter, "escalator"):
            cast(Any, adapter).escalator = escalator
        last_outcome = SourceOutcome.NOT_ATTEMPTED
        found: list[ListingCandidate] = []
        pages = 0
        work_skipped = 0
        try:
            self.circuit.assert_closed(source_id)
        except CircuitOpen:
            last_outcome = SourceOutcome.BLOCKED_BY_ACCESS
            events.blocked(source_id, last_outcome.value, "circuit open")
            self._finish_run(search_id, run_id, source_id, last_outcome, pages, len(found), events)
            return last_outcome.value, found
        from searcher.index.consult import hydrate_from_index
        from searcher.index.store import WarmIndex, versions_from_settings
        from searcher.index.text import field_terms

        index = WarmIndex(self.repos)
        versions = versions_from_settings(self.controller.settings)
        for query in queries:
            if query.query_id not in plan.query_ids and plan.query_ids:
                continue
            if index.query_already_run(
                source_id=source_id, query_text=query.query_text, versions=versions
            ):
                work_skipped += 1
                for hit in index.search(field_terms(query.query_text), versions):
                    found.append(hydrate_from_index(self.controller, search_id, hit))
                last_outcome = (
                    SourceOutcome.SEARCHED_MATCHES_FOUND
                    if found
                    else SourceOutcome.SEARCHED_NO_MATCH
                )
                continue
            events.query_dispatch(source_id, query.query_text)
            page = adapter.discover(query, None)  # type: ignore[attr-defined]
            known = SourceOutcome._value2member_map_
            outcome = (
                SourceOutcome(page.outcome)
                if page.outcome in known
                else SourceOutcome.NOT_ATTEMPTED
            )
            if is_block(outcome) or outcome is SourceOutcome.AUTH_REQUIRED:
                last_outcome = outcome
                events.blocked(source_id, outcome.value, page.note)
                self.health.record(source_id, outcome, policy_disabled=not manifest.enabled)
                self._finish_run(
                    search_id, run_id, source_id, last_outcome, pages, len(found), events
                )  # noqa: E501
                return last_outcome.value, found
            index.record_query(
                source_id=source_id,
                query_text=query.query_text,
                versions=versions,
                pages=len(page.urls),
            )
            for url in page.urls:
                frontier.enqueue(
                    search_id=search_id,
                    source_id=source_id,
                    url=url,
                    kind=_kind_for_url(url),
                    depth=0 if "sitemap" in url or "search" in url or "api.php" in url else 1,
                    priority=compute_priority(expected_match_value=query.expected_gain),
                    payload={"query": query.query_text},
                )
        worked = 0
        while worked < self.max_work:
            cancel.raise_if_cancelled()
            batch = frontier.pop(self.batch_size)
            if not batch:
                break
            for item in batch:
                worked += 1
                try:
                    decision = self.admission.decide(item.url, manifest)
                    receipt = SourceAdmissionReceipt(
                        search_id=search_id,
                        source_id=source_id,
                        url=item.url,
                        decision=decision.outcome.value if not decision.allowed else "admitted",
                        basis=decision.basis,
                        robots_allowed=decision.robots_allowed,
                    ).seal()
                    self.controller.store_receipt(receipt)
                    if not decision.allowed:
                        last_outcome = decision.outcome
                        frontier.complete(
                            item,
                            outcome=decision.outcome.value,
                            state=FrontierState.BLOCKED,
                        )
                        events.blocked(source_id, decision.outcome.value, decision.basis)
                        continue
                    doc = self._fetch_item(adapter, escalator, item.url, manifest)
                    pages += 1
                    last_outcome = doc.result.outcome
                    events.page_fetched(source_id, item.url, last_outcome.value)
                    self.repos.insert_discovery_page(
                        DiscoveryPage(
                            page_id=new_id(),
                            search_id=search_id,
                            source_id=source_id,
                            url=item.url,
                            content_digest=doc.result.content_digest,
                            cursor=item.cursor,
                            outcome=last_outcome,
                            fetched_at=utc_now(),
                        )
                    )
                    if last_outcome is SourceOutcome.SEARCHED_MATCHES_FOUND:
                        parsed = adapter.parse(doc)  # type: ignore[attr-defined]
                        for raw in parsed:
                            candidate = adapter.normalize(raw)  # type: ignore[attr-defined]
                            found.append(candidate)
                            self.repos.upsert_candidate(search_id, candidate)
                            events.candidates_found(source_id, 1)
                            expandable = {WorkKind.QUERY, WorkKind.SITEMAP, WorkKind.PAGINATION}
                            if item.depth < 3 and item.kind in expandable:
                                child_url = candidate.canonical_url
                                if child_url and child_url != item.url:
                                    frontier.enqueue(
                                        search_id=search_id,
                                        source_id=source_id,
                                        url=child_url,
                                        kind=WorkKind.LISTING,
                                        depth=item.depth + 1,
                                        payload={"from": item.work_key},
                                    )
                        html = doc.body.decode("utf-8", errors="replace")
                        if item.kind is WorkKind.SITEMAP:
                            locs = filter_locs(
                                parse_sitemap_locs(doc.body, limit=80),
                                str((item.payload or {}).get("query") or ""),
                                list(manifest.listing_path_prefixes),
                            )
                            for loc in locs[:20]:
                                frontier.enqueue(
                                    search_id=search_id,
                                    source_id=source_id,
                                    url=loc,
                                    kind=WorkKind.LISTING,
                                    depth=item.depth + 1,
                                )
                        elif item.kind is WorkKind.QUERY and manifest.listing_path_prefixes:
                            prefixes = list(manifest.listing_path_prefixes)
                            for loc in listing_links(html, item.url, prefixes)[:8]:
                                frontier.enqueue(
                                    search_id=search_id,
                                    source_id=source_id,
                                    url=loc,
                                    kind=WorkKind.LISTING,
                                    depth=item.depth + 1,
                                )
                        frontier.complete(item, outcome=last_outcome.value)
                    elif is_block(last_outcome):
                        frontier.complete(
                            item,
                            outcome=last_outcome.value,
                            state=FrontierState.BLOCKED,
                            error_class=last_outcome.value,
                        )
                        events.blocked(
                            source_id,
                            last_outcome.value,
                            doc.result.classification_note or "",
                        )
                    else:
                        frontier.complete(
                            item,
                            outcome=last_outcome.value,
                            error_class=last_outcome.value,
                        )
                except BudgetExceeded:
                    frontier.complete(
                        item,
                        outcome=SourceOutcome.UNMEASURABLE.value,
                        state=FrontierState.BLOCKED,
                        error_class="BUDGET",
                    )
                    last_outcome = SourceOutcome.UNMEASURABLE
                    raise
                except CancelledError:
                    frontier.complete(
                        item,
                        outcome=SourceOutcome.NOT_ATTEMPTED.value,
                        state=FrontierState.CANCELLED,
                    )
                    raise
        if found:
            last_outcome = SourceOutcome.SEARCHED_MATCHES_FOUND
        elif last_outcome is SourceOutcome.NOT_ATTEMPTED:
            last_outcome = SourceOutcome.SEARCHED_NO_MATCH
        self.health.record(source_id, last_outcome)
        self._finish_run(
            search_id,
            run_id,
            source_id,
            last_outcome,
            pages,
            len(found),
            events,
            work_skipped=work_skipped,
        )
        return last_outcome.value, found

    def _fetch_item(
        self,
        adapter: Any,
        escalator: Escalator,
        url: str,
        manifest: SourceManifest,
    ) -> FetchedDocument:
        if (
            hasattr(adapter, "escalator")
            and adapter.escalator is not None
            and hasattr(adapter, "fetch")
        ):  # noqa: E501
            try:
                return adapter.fetch(url, FetchMode.HTTP)  # type: ignore[no-any-return]
            except RuntimeError:
                pass
        return escalator.fetch(url, manifest, source_id=manifest.source_id)

    def _finish_run(
        self,
        search_id: str,
        run_id: str,
        source_id: str,
        outcome: SourceOutcome,
        pages: int,
        matches: int,
        events: SourceEvents,
        *,
        work_skipped: int = 0,
    ) -> None:
        self.repos.upsert_source_run(
            search_id,
            run_id,
            source_id,
            cursor=None,
            last_outcome=outcome.value,
            payload={"pages": pages, "matches": matches, "work_skipped": work_skipped},
        )
        receipt = SourceRunReceipt(
            search_id=search_id,
            source_id=source_id,
            outcome=outcome.value,
            pages=pages,
            matches=matches,
            blocked_reason=outcome.value if is_block(outcome) else None,
            work_skipped=work_skipped,
        ).seal()
        self.controller.store_receipt(receipt)
        events.coverage(source_id, outcome.value, pages)
        events.complete(source_id, outcome.value)

    def live_check_all(
        self, search_id: str, candidates: list[ListingCandidate]
    ) -> list[ListingCandidate]:  # noqa: E501
        updated: list[ListingCandidate] = []
        escalator = Escalator(
            self.http,
            self.admission,
            self.cache,
            usage=self.controller.usage(search_id),
        )
        for candidate in candidates:
            try:
                adapter = resolve_adapter(candidate.source_adapter)
                manifest = _adapter_manifest(adapter)
            except KeyError:
                updated.append(candidate)
                continue
            fresh, _status = check_candidate(candidate, manifest, escalator)
            self.repos.upsert_candidate(search_id, fresh)
            updated.append(fresh)
        return updated
