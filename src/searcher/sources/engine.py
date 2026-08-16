"""Drive source runs from the Wave 1 campaign controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import (
    DocumentClass,
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
from searcher.receipts.base import ReceiptBase
from searcher.receipts.types import SourceAdmissionReceipt, SourceRunReceipt
from searcher.sources.adapters import resolve_adapter
from searcher.sources.admission import AdmissionGate
from searcher.sources.broker import Coverage, SourceBroker
from searcher.sources.browser import BrowserPool
from searcher.sources.cache import ResponseCache
from searcher.sources.cancel import RunCancel
from searcher.sources.circuit import CircuitBreaker, CircuitOpen
from searcher.sources.classify import (
    classify_acquired_document,
    host_of,
    looks_like_index_url,
)
from searcher.sources.events import SourceEvents
from searcher.sources.expand import (
    INDEX_EXPANSION_RECEIPT,
    ExpansionResult,
    attach_image_absence,
    candidate_from_member,
    expand_index,
    expansion_caps_from_env,
    member_from_frontier_payload,
    member_frontier_payload,
    raw_listing_from_member,
)
from searcher.sources.fetch_log import FetchLog
from searcher.sources.fetch_modes import Escalator, FetchedDocument
from searcher.sources.frontier import MAX_DEPTH, Frontier, FrontierItem, compute_priority
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
    expansions: list[dict[str, object]] = field(default_factory=list)


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
            "products.json",
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
        per_index_cap: int | None = None,
        per_campaign_cap: int | None = None,
    ) -> None:
        self.controller = controller
        self.http = http or HonestHttpClient()
        self.owns_http = http is None
        self.batch_size = batch_size
        self.max_work = max_work
        caps = expansion_caps_from_env()
        self.per_index_cap = caps.per_index if per_index_cap is None else per_index_cap
        self.per_campaign_cap = caps.per_campaign if per_campaign_cap is None else per_campaign_cap
        self._campaign_expanded = 0
        self._expansions: list[dict[str, object]] = []
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
        self.browsers: BrowserPool | None = None

    def close(self) -> None:
        if self.browsers is not None:
            self.browsers.close()
            self.browsers = None
        if self.owns_http:
            self.http.close()

    def _make_escalator(
        self,
        search_id: str,
        *,
        cancel: RunCancel | None = None,
        log: FetchLog | None = None,
    ) -> Escalator:
        if self.browsers is None:
            self.browsers = BrowserPool(user_agent=self.controller.settings.user_agent)
        return Escalator(
            self.http,
            self.admission,
            self.cache,
            browsers=self.browsers,
            fetch_log=log,
            usage=self.controller.usage(search_id),
            cancel=cancel,
        )

    def run(
        self,
        search_id: str,
        queries: list[QueryVariant],
        *,
        source_names: list[str] | None = None,
        include_disabled: bool = False,
        families: frozenset[str] | None = None,
    ) -> SourceRunSummary:
        usage = self.controller.usage(search_id)
        cancel = RunCancel(search_id, self.controller.cancellation)
        events = SourceEvents(self.controller, search_id)
        coverage = Coverage()
        self._campaign_expanded = 0
        self._expansions = []
        if source_names is not None:
            self.broker.names = tuple(source_names)
        plans = self.broker.plan(
            queries, usage, include_disabled=include_disabled, families=families
        )
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
            expansions=list(self._expansions),
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
        escalator = self._make_escalator(search_id, cancel=cancel, log=log)
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
                    depth=0
                    if any(
                        token in url for token in ("sitemap", "search", "api.php", "products.json")
                    )
                    else 1,
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
                    pages_delta, last_outcome = self._handle_item(
                        item=item,
                        adapter=adapter,
                        escalator=escalator,
                        manifest=manifest,
                        frontier=frontier,
                        search_id=search_id,
                        source_id=source_id,
                        events=events,
                        found=found,
                    )
                    pages += pages_delta
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

    def _handle_item(
        self,
        *,
        item: FrontierItem,
        adapter: Any,
        escalator: Escalator,
        manifest: SourceManifest,
        frontier: Frontier,
        search_id: str,
        source_id: str,
        events: SourceEvents,
        found: list[ListingCandidate],
    ) -> tuple[int, SourceOutcome]:
        if item.payload.get("from_index_feed") and item.payload.get("canonical_url"):
            self._materialize_feed_member(
                item=item,
                adapter=adapter,
                frontier=frontier,
                search_id=search_id,
                source_id=source_id,
                events=events,
                found=found,
            )
            return 0, SourceOutcome.SEARCHED_MATCHES_FOUND
        doc = self._fetch_item(adapter, escalator, item.url, manifest)
        events.page_fetched(source_id, item.url, doc.result.outcome.value)
        self.repos.insert_discovery_page(
            DiscoveryPage(
                page_id=new_id(),
                search_id=search_id,
                source_id=source_id,
                url=item.url,
                content_digest=doc.result.content_digest,
                cursor=item.cursor,
                outcome=doc.result.outcome,
                fetched_at=utc_now(),
            )
        )
        last_outcome = doc.result.outcome
        if last_outcome is SourceOutcome.SEARCHED_MATCHES_FOUND:
            self._ingest_document(
                item=item,
                doc=doc,
                adapter=adapter,
                manifest=manifest,
                frontier=frontier,
                search_id=search_id,
                source_id=source_id,
                events=events,
                found=found,
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
        return 1, last_outcome

    def _ingest_document(
        self,
        *,
        item: FrontierItem,
        doc: FetchedDocument,
        adapter: Any,
        manifest: SourceManifest,
        frontier: Frontier,
        search_id: str,
        source_id: str,
        events: SourceEvents,
        found: list[ListingCandidate],
    ) -> None:
        url = doc.final_url or doc.result.url or item.url
        prefixes = list(manifest.listing_path_prefixes)
        document = classify_acquired_document(
            url=url,
            body=doc.body,
            content_type=doc.result.content_type,
            listing_prefixes=prefixes,
        )
        if document is DocumentClass.INDEX or looks_like_index_url(url):
            self._expand_into_frontier(
                item=item,
                body=doc.body,
                manifest=manifest,
                frontier=frontier,
                search_id=search_id,
                source_id=source_id,
            )
            return
        if document is not DocumentClass.PRODUCT:
            return
        parsed = adapter.parse(doc)
        for raw in parsed:
            raw_url = str(raw.payload.get("canonical_url") or raw.url)
            if looks_like_index_url(raw_url):
                continue
            candidate = attach_image_absence(
                adapter.normalize(raw),
                raw,
            )
            if looks_like_index_url(candidate.canonical_url):
                continue
            found.append(candidate)
            self.repos.upsert_candidate(search_id, candidate)
            events.candidates_found(source_id, 1)

    def _expand_into_frontier(
        self,
        *,
        item: FrontierItem,
        body: bytes,
        manifest: SourceManifest,
        frontier: Frontier,
        search_id: str,
        source_id: str,
    ) -> None:
        allowed_hosts = set()
        for raw in (manifest.domain, host_of(item.url)):
            if not raw:
                continue
            allowed_hosts.add(raw.lower())
            if ":" in raw and raw.rsplit(":", 1)[-1].isdigit():
                allowed_hosts.add(raw.rsplit(":", 1)[0].lower())
        seen = self._seen_target_urls(search_id, frontier)
        result = expand_index(
            url=item.url,
            body=body,
            listing_prefixes=list(manifest.listing_path_prefixes),
            allowed_hosts=sorted(allowed_hosts),
            seen_urls=seen,
            per_index_cap=self.per_index_cap,
            per_campaign_cap=self.per_campaign_cap,
            campaign_taken=self._campaign_expanded,
            child_depth=item.depth + 1,
            max_depth=MAX_DEPTH,
        )
        self._campaign_expanded = result.campaign_taken_after
        self._record_expansion(search_id, source_id, result)
        for member in result.taken:
            payload = member_frontier_payload(member, index_url=item.url, work_key=item.work_key)
            frontier.enqueue(
                search_id=search_id,
                source_id=source_id,
                url=member.url,
                kind=WorkKind.LISTING,
                depth=item.depth + 1,
                payload=payload,
            )

    def _materialize_feed_member(
        self,
        *,
        item: FrontierItem,
        adapter: Any,
        frontier: Frontier,
        search_id: str,
        source_id: str,
        events: SourceEvents,
        found: list[ListingCandidate],
    ) -> None:
        member = member_from_frontier_payload(item.payload, item.url)
        if looks_like_index_url(member.url):
            frontier.complete(item, outcome=SourceOutcome.SEARCHED_NO_MATCH.value)
            return
        language = None
        try:
            languages = adapter.manifest().languages
            if languages:
                language = languages[0]
        except Exception:
            language = None
        if hasattr(adapter, "normalize"):
            raw = raw_listing_from_member(member, source_adapter=source_id, language=language)
            candidate = attach_image_absence(adapter.normalize(raw), raw)
        else:
            candidate = candidate_from_member(member, source_adapter=source_id, language=language)
        if looks_like_index_url(candidate.canonical_url):
            frontier.complete(item, outcome=SourceOutcome.SEARCHED_NO_MATCH.value)
            return
        found.append(candidate)
        self.repos.upsert_candidate(search_id, candidate)
        events.candidates_found(source_id, 1)
        frontier.complete(item, outcome=SourceOutcome.SEARCHED_MATCHES_FOUND.value)

    def _seen_target_urls(self, search_id: str, frontier: Frontier) -> set[str]:
        from searcher.normalization.url import canonicalize_url

        seen: set[str] = set()
        for candidate in self.repos.list_candidates(search_id):
            if candidate.canonical_url:
                seen.add(canonicalize_url(candidate.canonical_url))
        for existing in frontier.list_all():
            if existing.url:
                seen.add(canonicalize_url(existing.url))
        return seen

    def _record_expansion(self, search_id: str, source_id: str, result: ExpansionResult) -> None:
        payload = result.as_payload()
        payload["source_id"] = source_id
        self._expansions.append(payload)
        receipt = ReceiptBase(
            receipt_type=INDEX_EXPANSION_RECEIPT,
            search_id=search_id,
            payload=payload,
        ).seal()
        self.controller.store_receipt(receipt)
        runtime = self.repos.get_runtime(search_id)
        recorded = list(runtime.get("index_expansions") or [])
        recorded.append(payload)
        runtime["index_expansions"] = recorded
        self.repos.update_runtime(search_id, runtime)

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
        return escalator.fetch(url, manifest, source_id=manifest.source_id, allow_render=True)

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
            payload={
                "pages": pages,
                "matches": matches,
                "work_skipped": work_skipped,
                "expansions": list(self._expansions),
            },
        )
        receipt = SourceRunReceipt(
            search_id=search_id,
            source_id=source_id,
            outcome=outcome.value,
            pages=pages,
            matches=matches,
            blocked_reason=outcome.value if is_block(outcome) else None,
            work_skipped=work_skipped,
            payload={"expansions": list(self._expansions)},
        ).seal()
        self.controller.store_receipt(receipt)
        events.coverage(source_id, outcome.value, pages)
        events.complete(source_id, outcome.value)

    def live_check_all(
        self, search_id: str, candidates: list[ListingCandidate]
    ) -> list[ListingCandidate]:  # noqa: E501
        updated: list[ListingCandidate] = []
        escalator = self._make_escalator(search_id)
        for candidate in candidates:
            try:
                adapter = resolve_adapter(candidate.source_adapter)
                manifest = _adapter_manifest(adapter)
            except KeyError:
                updated.append(candidate)
                continue
            try:
                fresh, _status = check_candidate(candidate, manifest, escalator)
            except BudgetExceeded:
                updated.append(candidate)
                seen = {item.candidate_id for item in updated}
                updated.extend(item for item in candidates if item.candidate_id not in seen)
                return updated
            self.repos.upsert_candidate(search_id, fresh)
            updated.append(fresh)
        return updated

    def verify_all(
        self, search_id: str, candidates: list[ListingCandidate]
    ) -> list[ListingCandidate]:
        from searcher.verification.runner import verify_candidates

        escalator = self._make_escalator(search_id)
        return verify_candidates(
            search_id,
            candidates,
            escalator,
            resolve_adapter,
            _adapter_manifest,
            repos=self.repos,
        )
