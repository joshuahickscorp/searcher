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
from searcher.sources.catalog import (
    CATALOG_FALLBACK_RECEIPT,
    CatalogCaps,
    CatalogResult,
    catalog_caps_from_env,
    catalog_feed_path_of,
    catalog_page_param_of,
    catalog_page_size_of,
    catalog_url_allowed,
    origin_for_spec,
    page_catalog,
)
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
from searcher.sources.platform import (
    admitted_hosts_for,
    commerce_origins_for,
    robots_evidence,
    strategy_origins_for,
)
from searcher.sources.robots import RobotsCache
from searcher.sources.statuses import is_block
from searcher.sources.strategies import (
    CATALOG_FEED,
    COLLECTION_SLUG,
    OFFICIAL_API,
    SITE_SEARCH,
    SITEMAP,
    STATUS_BLOCKED,
    STATUS_QUEUED,
    STATUS_SKIPPED,
    StrategyBook,
    plan_strategies,
    strategy_name_for_url,
    strategy_url_allowed,
)


@dataclass
class SourceRunSummary:
    search_id: str
    coverage: dict[str, str]
    candidates_before: int
    candidates_after: int
    listings: list[ListingCandidate] = field(default_factory=list)
    blocked: list[dict[str, str]] = field(default_factory=list)
    expansions: list[dict[str, object]] = field(default_factory=list)
    catalog_fallbacks: list[dict[str, object]] = field(default_factory=list)
    strategy_coverage: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    coverage_details: dict[str, str] = field(default_factory=dict)


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


# Catalogue walks default to 64 pages/source and 80/campaign, which is more
# than a 40-page campaign can give. Share what remains so one source cannot
# spend the campaign. Floor keeps a useful walk when N is large.
CATALOG_PAGE_SHARE_FLOOR = 2


def remaining_page_budget(usage: Any) -> int:
    """Pages still allowed by the sealed campaign budget."""
    try:
        ceiling = int(usage.sealed.ceiling("pages"))
        used = int(usage.used("pages"))
    except (AttributeError, TypeError, ValueError, KeyError):
        return 0
    return max(0, ceiling - used)


def catalog_page_share(remaining_pages: int, source_count: int) -> int:
    """Per-source catalogue pages: max(floor, remaining // N).

    On a 40-page campaign with 9 sources this is 4. A single source that
    used the env default of 64 spent the campaign before the others ran.
    """
    if remaining_pages <= 0 or source_count <= 0:
        return 0
    return max(CATALOG_PAGE_SHARE_FLOOR, remaining_pages // source_count)


def catalog_caps_for_campaign(remaining_pages: int, source_count: int) -> CatalogCaps:
    """Bind env catalogue caps to a fair share of the remaining page budget."""
    env = catalog_caps_from_env()
    share = catalog_page_share(remaining_pages, source_count)
    return CatalogCaps(
        pages_per_source=min(env.pages_per_source, share),
        pages_per_campaign=min(env.pages_per_campaign, max(0, remaining_pages)),
        promote_per_source=env.promote_per_source,
        promote_per_campaign=env.promote_per_campaign,
    )


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
        self._campaign_query_texts: list[str] = []
        self._expansions: list[dict[str, object]] = []
        self._campaign_catalog_pages = 0
        self._campaign_catalog_promoted = 0
        self._catalogs: list[dict[str, object]] = []
        self._catalog_walk_caps: CatalogCaps | None = None
        self._strategy_books: dict[str, StrategyBook] = {}
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

    def _intent_terms(self, search_id: str) -> list[str]:
        """The user's own text and tags, if the campaign still holds them."""
        try:
            intent = self.controller.repos.get_intent(search_id)
        except Exception:
            return []
        if intent is None:
            return []
        terms: list[str] = []
        text = getattr(intent, "text", None)
        if text:
            terms.append(str(text))
        for tag in getattr(intent, "tags", None) or []:
            if str(tag).strip():
                terms.append(str(tag))
        return terms

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
        # Feed-order sampling of a large collection misses the item being
        # searched for; expansion ranks members against these before capping.
        # Compiled queries are hypotheses about the item; the words the user
        # actually typed are evidence about it. Ranking a collection by the
        # hypotheses alone missed a listing titled ハイヒールパンプス because no
        # compiled query contained that word, while the user's own text did.
        self._campaign_query_texts = [
            item.query_text for item in queries if str(item.query_text or "").strip()
        ]
        self._campaign_query_texts.extend(self._intent_terms(search_id))
        self._expansions = []
        self._campaign_catalog_pages = 0
        self._campaign_catalog_promoted = 0
        self._catalogs = []
        self._catalog_walk_caps = None
        self._strategy_books = {}
        if source_names is not None:
            self.broker.names = tuple(source_names)
        plans = self.broker.plan(
            queries,
            usage,
            include_disabled=include_disabled,
            families=families,
            coverage=coverage,
        )
        # Bound each catalogue walk to a share of the remaining page budget
        # before any source runs. The env default (64) is larger than the
        # campaign page_limit (40); without this the first source spends it.
        self._bind_catalog_walk_caps(usage, len(plans))
        all_candidates: list[ListingCandidate] = []
        blocked: list[dict[str, str]] = []
        def _record_unattempted(remaining: list[Any], why: str) -> None:
            for skipped in remaining:
                coverage.record(
                    skipped.source_adapter,
                    SourceOutcome.NOT_ATTEMPTED,
                    detail=why,
                )

        for index, plan in enumerate(plans):
            cancel.raise_if_cancelled()
            try:
                usage.consume(sources=1)
            except BudgetExceeded:
                coverage.record(plan.source_adapter, SourceOutcome.UNMEASURABLE)
                _record_unattempted(plans[index + 1 :], "source budget exhausted")
                break
            try:
                summary, found = self._run_plan(search_id, plan, queries, events, cancel)
            except BudgetExceeded:
                # A page-budget exhaustion inside one source used to unwind out
                # of run() entirely, so every source after it vanished: a live
                # campaign planned nine, completed one, and reported zero
                # blocked. The reader was told "it is a different product" about
                # eight candidates while the source holding their item had never
                # been opened. A budget that runs out is a fact to report, not a
                # reason to stop reporting.
                coverage.record(
                    plan.source_adapter,
                    SourceOutcome.UNMEASURABLE,
                    detail="budget exhausted while this source was being searched",
                )
                _record_unattempted(
                    plans[index + 1 :],
                    "not attempted: the campaign budget was exhausted by an earlier source",
                )
                break
            book = self._strategy_books.get(plan.source_adapter)
            coverage.record(
                plan.source_adapter,
                SourceOutcome(summary),
                detail=book.detail() if book is not None else "",
                strategies=book.as_payload() if book is not None else None,
            )
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
        runtime["coverage_details"] = dict(coverage.details)
        runtime["reach_strategies"] = {
            source_id: list(items) for source_id, items in coverage.strategies.items()
        }
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
            catalog_fallbacks=list(self._catalogs),
            strategy_coverage=dict(coverage.strategies),
            coverage_details=dict(coverage.details),
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
        book = StrategyBook(source_id)
        self._strategy_books[source_id] = book
        spec = getattr(adapter, "spec", None)
        if spec is not None:
            seed_text = next(
                (str(item.query_text) for item in queries if str(item.query_text or "").strip()),
                "",
            )
            book.load_plan(plan_strategies(spec, seed_text))
            self._seed_robots_sitemaps(
                spec=spec,
                manifest=manifest,
                frontier=frontier,
                search_id=search_id,
                source_id=source_id,
                book=book,
                query_gain=next((item.expected_gain for item in queries), 0.0),
            )
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
                if outcome is SourceOutcome.AUTH_REQUIRED:
                    book.record(
                        OFFICIAL_API,
                        status=STATUS_BLOCKED,
                        reason=page.note or "AUTH_REQUIRED",
                    )
                elif not book.attempts:
                    book.record(
                        source_id,
                        status=STATUS_BLOCKED,
                        reason=page.note or outcome.value,
                    )
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
        if self._should_run_catalog(adapter, source_id):
            extra_pages, catalog_outcome = self._run_catalog_fallback(
                adapter=adapter,
                escalator=escalator,
                manifest=manifest,
                queries=queries,
                search_id=search_id,
                source_id=source_id,
                events=events,
                found=found,
                frontier=frontier,
            )
            pages += extra_pages
            if found:
                last_outcome = SourceOutcome.SEARCHED_MATCHES_FOUND
            elif catalog_outcome is not SourceOutcome.NOT_ATTEMPTED:
                last_outcome = catalog_outcome
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
                    worked = self.max_work
                    break
                except CancelledError:
                    frontier.complete(
                        item,
                        outcome=SourceOutcome.NOT_ATTEMPTED.value,
                        state=FrontierState.CANCELLED,
                    )
                    raise
            else:
                continue
            break
        self._finalize_strategy_yields(source_id, book)
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
                spec=getattr(adapter, "spec", None),
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
        spec: object | None = None,
    ) -> None:
        allowed_hosts: set[str] = set()
        if spec is not None:
            allowed_hosts.update(admitted_hosts_for(spec, manifest))
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
            query_texts=self._campaign_query_texts,
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

    def _seed_robots_sitemaps(
        self,
        *,
        spec: object,
        manifest: SourceManifest,
        frontier: Frontier,
        search_id: str,
        source_id: str,
        book: StrategyBook,
        query_gain: float,
    ) -> None:
        """Enqueue sitemaps declared in a fetched robots.txt. Report what was fetched."""
        disallowed = tuple(getattr(spec, "disallowed", ()) or ())
        extra: list[str] = []
        evidence: list[dict[str, object]] = []
        for origin in commerce_origins_for(spec):
            if not origin:
                continue
            probe = f"{origin}/"
            try:
                decision = self.admission.decide(probe, manifest)
            except Exception:
                evidence.append(
                    robots_evidence(origin=origin, body="", status="fetch_failed")
                )
                continue
            cached = self.robots.get_cached(origin)
            status = "missing"
            body = ""
            if cached is not None:
                status = cached.status
                body = cached.body
            elif decision.robots_fetch_status:
                status = decision.robots_fetch_status
            evidence.append(robots_evidence(origin=origin, body=body, status=status))
            if cached is None or cached.status != "ok":
                continue
            for sitemap in cached.sitemaps:
                if not sitemap or not strategy_url_allowed(sitemap, disallowed):
                    continue
                extra.append(sitemap)
        if evidence:
            runtime = self.repos.get_runtime(search_id)
            recorded = list(runtime.get("robots_evidence") or [])
            recorded.extend(evidence)
            runtime["robots_evidence"] = recorded
            self.repos.update_runtime(search_id, runtime)
        if not extra:
            return
        existing = book.attempts.get(SITEMAP)
        known = set(existing.urls) if existing is not None else set()
        added = [url for url in extra if url not in known]
        if not added:
            return
        if existing is None or existing.status in {STATUS_SKIPPED, STATUS_BLOCKED}:
            book.record(
                SITEMAP,
                status=STATUS_QUEUED,
                reason="robots-declared sitemap",
                urls=added,
            )
        else:
            existing.urls = list(existing.urls) + added
            if existing.status != STATUS_QUEUED:
                existing.status = STATUS_QUEUED
                existing.reason = "robots-declared sitemap"
        for url in added:
            frontier.enqueue(
                search_id=search_id,
                source_id=source_id,
                url=url,
                kind=_kind_for_url(url),
                depth=0,
                priority=compute_priority(expected_match_value=query_gain),
            )

    def _should_run_catalog(self, adapter: Any, source_id: str) -> bool:
        """Catalogue feed is a first-class strategy, not a last-ditch fallback.

        A guessed collection handle that happens to exist can still miss the
        item. The shop-wide feed is searched whenever the source publishes one.
        """
        spec = getattr(adapter, "spec", None)
        if spec is None or catalog_feed_path_of(spec) is None:
            return False
        book = self._strategy_books.get(source_id)
        if book is not None:
            planned = book.attempts.get(CATALOG_FEED)
            if planned is not None and planned.status != "queued":
                return False
        return True

    def _finalize_strategy_yields(self, source_id: str, book: StrategyBook) -> None:
        counts = {COLLECTION_SLUG: 0, SITE_SEARCH: 0, SITEMAP: 0, CATALOG_FEED: 0}
        reasons = {
            COLLECTION_SLUG: "collection handle had no matching products",
            SITE_SEARCH: "site search returned no listing URLs",
            SITEMAP: "sitemap locs did not match the query",
            CATALOG_FEED: "catalogue feed text matched no products",
        }
        for payload in self._expansions:
            if payload.get("source_id") != source_id:
                continue
            index_url = str(payload.get("index_url") or "")
            name = strategy_name_for_url(index_url) if index_url else COLLECTION_SLUG
            taken = payload.get("taken")
            members = payload.get("members_found")
            taken_n = taken if isinstance(taken, int) else 0
            if name in counts:
                counts[name] += taken_n
                if taken_n == 0:
                    drop = payload.get("drop_reasons")
                    if isinstance(drop, dict) and drop.get("query_not_in_loc"):
                        reasons[name] = "sitemap locs did not contain query tokens"
                    elif isinstance(members, int) and members == 0:
                        reasons[name] = "strategy URL contained no listing members"
        for payload in self._catalogs:
            if payload.get("source_id") != source_id:
                continue
            promoted = payload.get("products_promoted")
            counts[CATALOG_FEED] = int(promoted) if isinstance(promoted, int) else 0
            if counts[CATALOG_FEED] == 0:
                stopped = str(payload.get("stopped_reason") or "")
                drops = payload.get("drop_reasons")
                if stopped == "robots_disallowed":
                    reasons[CATALOG_FEED] = "robots disallowed the catalogue feed"
                elif stopped == "no_query":
                    reasons[CATALOG_FEED] = "no query text to match against the feed"
                elif isinstance(drops, dict) and drops.get("feed_text_no_match"):
                    reasons[CATALOG_FEED] = (
                        f"feed text matched none of {drops.get('feed_text_no_match')} products"
                    )
                elif stopped:
                    reasons[CATALOG_FEED] = f"catalogue stopped: {stopped}"
        for name, yielded in counts.items():
            if name not in book.attempts:
                continue
            if yielded > 0:
                book.mark_tried(name, yielded=yielded, reason="promoted listing URLs")
            else:
                book.mark_tried(name, yielded=0, reason=reasons[name])

    def _bind_catalog_walk_caps(self, usage: Any, source_count: int) -> None:
        """Share remaining pages across planned sources. Called from both run()s."""
        self._catalog_walk_caps = catalog_caps_for_campaign(
            remaining_page_budget(usage), source_count
        )

    def _run_catalog_fallback(
        self,
        *,
        adapter: Any,
        escalator: Escalator,
        manifest: SourceManifest,
        queries: list[QueryVariant],
        search_id: str,
        source_id: str,
        events: SourceEvents,
        found: list[ListingCandidate],
        frontier: Frontier,
    ) -> tuple[int, SourceOutcome]:
        spec = getattr(adapter, "spec", None)
        feed_path = catalog_feed_path_of(spec) if spec is not None else None
        if spec is None or not feed_path:
            return 0, SourceOutcome.NOT_ATTEMPTED
        disallowed = list(getattr(spec, "disallowed", ()) or ())
        origins = list(strategy_origins_for(spec))
        recorded = origin_for_spec(spec, fallback=f"https://{manifest.domain}")
        if recorded and recorded not in origins:
            origins.append(recorded)
        if not origins and recorded:
            origins = [recorded]
        allowed_hosts = set(admitted_hosts_for(spec, manifest))
        for raw in (manifest.domain, *(host_of(item) for item in origins)):
            if raw:
                allowed_hosts.add(raw.lower())
        seen = self._seen_target_urls(search_id, frontier)
        query_texts = list(self._campaign_query_texts)
        if not query_texts:
            query_texts = [
                item.query_text for item in queries if str(item.query_text or "").strip()
            ]

        def fetch_page(url: str) -> bytes:
            if not catalog_url_allowed(url, disallowed):
                return b""
            doc = self._fetch_item(adapter, escalator, url, manifest)
            events.page_fetched(source_id, url, doc.result.outcome.value)
            self.repos.insert_discovery_page(
                DiscoveryPage(
                    page_id=new_id(),
                    search_id=search_id,
                    source_id=source_id,
                    url=url,
                    content_digest=doc.result.content_digest,
                    cursor=None,
                    outcome=doc.result.outcome,
                    fetched_at=utc_now(),
                )
            )
            if doc.result.outcome is SourceOutcome.SEARCHED_MATCHES_FOUND:
                return doc.body
            return b""

        pages_read = 0
        last_result: CatalogResult | None = None
        chosen: CatalogResult | None = None
        picked: CatalogResult | None = None
        for origin in origins:
            result = page_catalog(
                origin=origin,
                feed_path=feed_path,
                query_texts=query_texts,
                fetch_page=fetch_page,
                disallowed=disallowed,
                page_param=catalog_page_param_of(spec),
                page_size=catalog_page_size_of(spec),
                caps=self._catalog_walk_caps,
                campaign_pages_already=self._campaign_catalog_pages,
                campaign_promoted_already=self._campaign_catalog_promoted,
                seen_urls=seen,
                allowed_hosts=sorted(allowed_hosts),
                source_id=source_id,
            )
            self._campaign_catalog_pages = result.campaign_pages_after
            self._campaign_catalog_promoted = result.campaign_promoted_after
            self._record_catalog(search_id, source_id, result)
            pages_read += result.pages_read
            last_result = result
            if result.products_promoted > 0 or result.products_seen > 0:
                chosen = result
                break
            if result.stopped_reason == "robots_disallowed":
                continue
        picked = chosen or last_result
        if picked is None:
            return 0, SourceOutcome.NOT_ATTEMPTED
        result = picked
        language = None
        try:
            languages = adapter.manifest().languages
            if languages:
                language = languages[0]
        except Exception:
            language = None
        for member in result.promoted:
            if looks_like_index_url(member.url):
                continue
            if hasattr(adapter, "normalize"):
                listing = raw_listing_from_member(
                    member, source_adapter=source_id, language=language
                )
                candidate = attach_image_absence(adapter.normalize(listing), listing)
            else:
                candidate = candidate_from_member(
                    member, source_adapter=source_id, language=language
                )
            if looks_like_index_url(candidate.canonical_url):
                continue
            found.append(candidate)
            self.repos.upsert_candidate(search_id, candidate)
            events.candidates_found(source_id, 1)
        if result.products_promoted > 0:
            return pages_read, SourceOutcome.SEARCHED_MATCHES_FOUND
        if result.stopped_reason == "robots_disallowed" and result.products_seen == 0:
            return pages_read, SourceOutcome.BLOCKED_BY_POLICY
        return pages_read, SourceOutcome.SEARCHED_NO_MATCH

    def _record_catalog(self, search_id: str, source_id: str, result: CatalogResult) -> None:
        payload = result.as_payload()
        payload["source_id"] = source_id
        payload["catalog_fallback"] = True
        self._catalogs.append(payload)
        receipt = ReceiptBase(
            receipt_type=CATALOG_FALLBACK_RECEIPT,
            search_id=search_id,
            payload=payload,
        ).seal()
        self.controller.store_receipt(receipt)
        runtime = self.repos.get_runtime(search_id)
        recorded = list(runtime.get("catalog_fallbacks") or [])
        recorded.append(payload)
        runtime["catalog_fallbacks"] = recorded
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
        book = self._strategy_books.get(source_id)
        strategies = book.as_payload() if book is not None else []
        detail = book.detail() if book is not None else ""
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
                "catalog_fallbacks": list(self._catalogs),
                "strategies": strategies,
                "strategy_detail": detail,
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
            payload={
                "expansions": list(self._expansions),
                "catalog_fallbacks": list(self._catalogs),
                "strategies": strategies,
                "strategy_detail": detail,
            },
        ).seal()
        self.controller.store_receipt(receipt)
        events.coverage(source_id, outcome.value, pages, strategies=strategies, detail=detail)
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
