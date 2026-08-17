"""Campaign-entry deadlines and host-aware concurrent discovery.

The HTTP client, escalator, and engine live in a lane this worker may not
edit. Those layers retry a timed-out fetch up to four times with backoff
and walk sources one by one with no per-source ceiling, so a single silent
host holds DISCOVERING at "Searching international sources" for ~90s.

This wrapper is the worker's deadline and the honest speed lever: each
source gets a wall budget, independent hosts overlap, each host stays
inside its own concurrent/rpm/crawl-delay cap, retries stop when the
budget is gone, and a stall is recorded as SOURCE_UNAVAILABLE with the
elapsed time. Robots checks still run on every URL.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import Any

import httpx

from searcher.contracts.enums import FetchMode, SourceOutcome
from searcher.contracts.models import (
    FetchResult,
    ListingCandidate,
    QueryVariant,
    SourceManifest,
    SourcePlan,
)
from searcher.core.deadlines import (
    RETRY_REMAINING_FLOOR_SECONDS,
    connect_timeout_seconds,
    default_request_timeout,
    default_source_deadline,
)
from searcher.core.errors import BudgetExceeded, CancelledError, ErrorClass
from searcher.core.ids import new_id
from searcher.deduplication.clusters import cluster_candidates
from searcher.sources.broker import Coverage
from searcher.sources.cancel import RunCancel
from searcher.sources.classify import host_of
from searcher.sources.engine import DiscoveryEngine, SourceRunSummary
from searcher.sources.events import SourceEvents
from searcher.sources.fetch_modes import Escalator, FetchedDocument
from searcher.sources.http import FetchError, HonestHttpClient
from searcher.sources.live_check import check_candidate
from searcher.sources.statuses import is_block
from searcher.workers.host_io import concurrent_cap, map_by_host
from searcher.workers.locks import LockedController

DEADLINE_REASON = "source deadline exceeded"


class _PerRequestTimeout:
    """httpx.Client stand-in that stamps a fresh timeout on every request."""

    def __init__(self, inner: httpx.Client, timeout_fn: Callable[[], httpx.Timeout]) -> None:
        self._inner = inner
        self._timeout_fn = timeout_fn

    def request(self, *args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", self._timeout_fn())
        return self._inner.request(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

_retry_state = threading.local()
_retry_wrap_lock = threading.Lock()
_retry_wrapped = False


class DeadlineHttpClient(HonestHttpClient):
    """HonestHttpClient whose connect/read/total budgets shrink with the source."""

    def __init__(
        self,
        *,
        timeout: float | None = None,
        connect_timeout: float | None = None,
        transport: httpx.BaseTransport | None = None,
        user_agent: str | None = None,
        max_bytes: int | None = None,
        max_redirects: int | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"timeout": float(timeout or default_request_timeout())}
        if transport is not None:
            kwargs["transport"] = transport
        if user_agent is not None:
            kwargs["user_agent"] = user_agent
        if max_bytes is not None:
            kwargs["max_bytes"] = max_bytes
        if max_redirects is not None:
            kwargs["max_redirects"] = max_redirects
        super().__init__(**kwargs)
        self.connect_timeout = float(connect_timeout or connect_timeout_seconds())
        self._local = threading.local()
        wrapped_client = _PerRequestTimeout(self._client, self._request_timeout)
        object.__setattr__(self, "_client", wrapped_client)

    def set_deadline(self, when: float | None) -> None:
        self._local.deadline_at = when

    def clear_deadline(self) -> None:
        self._local.deadline_at = None

    @property
    def deadline_tripped(self) -> bool:
        return bool(getattr(self._local, "deadline_tripped", False))

    @deadline_tripped.setter
    def deadline_tripped(self, value: bool) -> None:
        self._local.deadline_tripped = bool(value)

    def remaining(self) -> float | None:
        deadline_at = getattr(self._local, "deadline_at", None)
        if deadline_at is None:
            return None
        return float(deadline_at) - time.monotonic()

    def _request_timeout(self) -> httpx.Timeout:
        remaining = self.remaining()
        total = float(self.timeout)
        connect = self.connect_timeout
        if remaining is not None:
            total = max(RETRY_REMAINING_FLOOR_SECONDS, min(total, remaining))
            connect = min(connect, total)
        return httpx.Timeout(total, connect=min(connect, total))

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Any = None,
        base_delay: float = 1.0,
        extra_headers: Any = None,
        if_none_match: str | None = None,
        if_modified_since: str | None = None,
        pace: bool = True,
    ) -> Any:
        remaining = self.remaining()
        if remaining is not None and remaining <= RETRY_REMAINING_FLOOR_SECONDS:
            self.deadline_tripped = True
            raise FetchError(DEADLINE_REASON, error_class=ErrorClass.TIMEOUT)
        if pace:
            wait = self._pace_wait(url, base_delay)
            if remaining is not None and wait > remaining:
                self.deadline_tripped = True
                raise FetchError(
                    f"{DEADLINE_REASON} waiting {wait:.2f}s on host rate",
                    error_class=ErrorClass.TIMEOUT,
                )
            if wait > 0:
                time.sleep(wait)
        return super().request(
            method,
            url,
            headers=headers,
            base_delay=base_delay,
            extra_headers=extra_headers,
            if_none_match=if_none_match,
            if_modified_since=if_modified_since,
            pace=False,
        )

    def _pace_wait(self, url: str, base_delay: float) -> float:
        limiter = self.limiter_for(url, base_delay)
        with limiter.lock:
            now = time.monotonic()
            elapsed = now - limiter.last_at
            jittered = limiter.base_delay * random.uniform(0.7, 1.3)
            if elapsed >= jittered:
                limiter.last_at = now
                return 0.0
            wait = jittered - elapsed
            limiter.last_at = now + wait
            return wait


def _install_thread_retries() -> None:
    """Wrap retry helpers once. Each thread supplies its own remaining budget."""
    global _retry_wrapped
    if _retry_wrapped:
        return
    import searcher.sources.fetch_modes as fetch_modes

    with _retry_wrap_lock:
        if _retry_wrapped:
            return
        orig_retry = fetch_modes.should_retry  # type: ignore[attr-defined]
        orig_backoff = fetch_modes.backoff_seconds  # type: ignore[attr-defined]

        def gated_retry(outcome: SourceOutcome, attempt: int, **kwargs: Any) -> bool:
            remaining_fn = getattr(_retry_state, "remaining_fn", None)
            if remaining_fn is not None and remaining_fn() <= RETRY_REMAINING_FLOOR_SECONDS:
                return False
            return bool(orig_retry(outcome, attempt, **kwargs))

        def gated_backoff(attempt: int, retry_after: float | None = None) -> float:
            delay = float(orig_backoff(attempt, retry_after))
            remaining_fn = getattr(_retry_state, "remaining_fn", None)
            if remaining_fn is None:
                return delay
            left = float(remaining_fn())
            if left <= 0:
                return 0.0
            return min(delay, left)

        fetch_modes.should_retry = gated_retry  # type: ignore[attr-defined]
        fetch_modes.backoff_seconds = gated_backoff  # type: ignore[attr-defined]
        _retry_wrapped = True


@contextmanager
def _bound_retries(remaining_fn: Callable[[], float]) -> Iterator[None]:
    _install_thread_retries()
    previous = getattr(_retry_state, "remaining_fn", None)
    _retry_state.remaining_fn = remaining_fn
    try:
        yield
    finally:
        _retry_state.remaining_fn = previous


class _SingleLimiterEscalator(Escalator):
    """Drop the extra token bucket. HTTP already paces crawl-delay / rpm."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "host_limiter", None)


class _ReplayEscalator:
    """Return a document already fetched. Verification must not GET the URL twice."""

    def __init__(self, doc: FetchedDocument) -> None:
        self._doc = doc

    def fetch(self, *args: Any, **kwargs: Any) -> FetchedDocument:
        del args, kwargs
        return self._doc


class BoundedDiscoveryEngine(DiscoveryEngine):
    """DiscoveryEngine with per-source deadlines and host-aware overlap."""

    _default_source_deadline: float | None = None
    _default_request_timeout: float | None = None

    def __init__(
        self,
        controller: Any,
        *,
        http: HonestHttpClient | None = None,
        batch_size: int = 4,
        max_work: int = 40,
        source_deadline_seconds: float | None = None,
        request_timeout_seconds: float | None = None,
    ) -> None:
        resolved_deadline = source_deadline_seconds
        if resolved_deadline is None:
            resolved_deadline = type(self)._default_source_deadline
        if resolved_deadline is None:
            resolved_deadline = default_source_deadline()
        resolved_timeout = request_timeout_seconds
        if resolved_timeout is None:
            resolved_timeout = type(self)._default_request_timeout
        if resolved_timeout is None:
            resolved_timeout = default_request_timeout()
        self.source_deadline_seconds = float(resolved_deadline)
        self.request_timeout_seconds = float(resolved_timeout)
        self._local = threading.local()
        self._state_lock = threading.RLock()
        if isinstance(controller, LockedController):
            wrapped = controller
        else:
            wrapped = LockedController(controller)
        if http is None:
            http = DeadlineHttpClient(timeout=self.request_timeout_seconds)
        super().__init__(wrapped, http=http, batch_size=batch_size, max_work=max_work)  # type: ignore[arg-type]

    def _make_escalator(
        self,
        search_id: str,
        *,
        cancel: RunCancel | None = None,
        log: Any = None,
    ) -> Escalator:
        if self.browsers is None:
            from searcher.sources.browser import BrowserPool

            with self._state_lock:
                if self.browsers is None:
                    self.browsers = BrowserPool(user_agent=self.controller.settings.user_agent)
        return _SingleLimiterEscalator(
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
        self._campaign_query_texts = [
            item.query_text for item in queries if str(item.query_text or "").strip()
        ]
        self._campaign_query_texts.extend(self._intent_terms(search_id))
        self._expansions = []
        self._campaign_catalog_pages = 0
        self._campaign_catalog_promoted = 0
        self._catalogs = []
        if source_names is not None:
            self.broker.names = tuple(source_names)
        plans = self.broker.plan(
            queries, usage, include_disabled=include_disabled, families=families
        )
        eligible: list[SourcePlan] = []
        for plan in plans:
            cancel.raise_if_cancelled()
            try:
                usage.consume(sources=1)
            except BudgetExceeded:
                coverage.record(plan.source_adapter, SourceOutcome.UNMEASURABLE)
                break
            eligible.append(plan)
        all_candidates: list[ListingCandidate] = []
        blocked: list[dict[str, str]] = []
        fatal: BaseException | None = None

        def one_plan(plan: SourcePlan) -> tuple[SourcePlan, str, list[ListingCandidate]]:
            summary, found = self._run_plan(search_id, plan, queries, events, cancel)
            return plan, summary, found

        results: list[tuple[SourcePlan, str, list[ListingCandidate]]] = []
        if len(eligible) <= 1:
            for plan in eligible:
                results.append(one_plan(plan))
        else:
            workers = min(8, len(eligible))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = {pool.submit(one_plan, plan): plan for plan in eligible}
                for fut in as_completed(futs):
                    try:
                        results.append(fut.result())
                    except CancelledError as exc:
                        fatal = exc
                    except BudgetExceeded as exc:
                        if fatal is None:
                            fatal = exc
                    except BaseException as exc:  # noqa: BLE001 — one source must not kill the rest
                        if fatal is None:
                            fatal = exc
        # Stable report order matches the broker plan order.
        by_adapter = {
            plan.source_adapter: (plan, summary, found) for plan, summary, found in results
        }
        for plan in eligible:
            row = by_adapter.get(plan.source_adapter)
            if row is None:
                continue
            _, summary, found = row
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
                },
            )
        runtime = self.controller.repos.get_runtime(search_id)
        runtime["coverage"] = coverage.per_source
        runtime["dedupe_savings"] = deduped.savings
        self.controller.repos.update_runtime(search_id, runtime)
        self.controller.persist_usage(search_id)
        run_summary = SourceRunSummary(
            search_id=search_id,
            coverage=coverage.per_source,
            candidates_before=before,
            candidates_after=len(deduped.representatives),
            listings=deduped.representatives,
            blocked=blocked,
            expansions=list(self._expansions),
            catalog_fallbacks=list(self._catalogs),
        )
        if isinstance(fatal, CancelledError):
            raise fatal
        if isinstance(fatal, BudgetExceeded):
            raise fatal
        return run_summary

    def _run_plan(
        self,
        search_id: str,
        plan: SourcePlan,
        queries: list[QueryVariant],
        events: SourceEvents,
        cancel: Any,
    ) -> tuple[str, list[Any]]:
        started = time.monotonic()
        deadline_at = started + self.source_deadline_seconds
        previous_deadline = getattr(self._local, "deadline_at", None)
        self._local.deadline_at = deadline_at
        self._local.cut_short = False
        setter = getattr(self.http, "set_deadline", None)
        if callable(setter):
            setter(deadline_at)
        elapsed = 0.0
        try:
            with _bound_retries(lambda: deadline_at - time.monotonic()):
                result = super()._run_plan(search_id, plan, queries, events, cancel)
        finally:
            clearer = getattr(self.http, "clear_deadline", None)
            if callable(clearer):
                clearer()
            elapsed = time.monotonic() - started
            self._local.deadline_at = previous_deadline
        tripped = bool(getattr(self._local, "cut_short", False)) or bool(
            getattr(self.http, "deadline_tripped", False)
        )
        if tripped:
            reason = f"{DEADLINE_REASON} after {elapsed:.2f}s"
            events.blocked(plan.source_adapter, SourceOutcome.SOURCE_UNAVAILABLE.value, reason)
            self._record_abandonment(search_id, plan.source_adapter, elapsed, reason)
        if hasattr(self.http, "deadline_tripped"):
            self.http.deadline_tripped = False
        self._local.cut_short = False
        return result

    def _fetch_item(
        self,
        adapter: Any,
        escalator: Escalator,
        url: str,
        manifest: SourceManifest,
    ) -> FetchedDocument:
        deadline_at = getattr(self._local, "deadline_at", None)
        if deadline_at is not None and deadline_at - time.monotonic() <= 0:
            self._local.cut_short = True
            return FetchedDocument(
                result=FetchResult(
                    attempt_id=new_id(),
                    url=url,
                    outcome=SourceOutcome.SOURCE_UNAVAILABLE,
                    classification_note=DEADLINE_REASON,
                    mode=FetchMode.HTTP,
                    error_class=ErrorClass.TIMEOUT.value,
                ),
                body=b"",
                headers={},
                final_url=url,
            )
        return super()._fetch_item(adapter, escalator, url, manifest)

    def _expand_into_frontier(self, **kwargs: Any) -> None:
        with self._state_lock:
            super()._expand_into_frontier(**kwargs)

    def _run_catalog_fallback(self, **kwargs: Any) -> tuple[int, SourceOutcome]:
        with self._state_lock:
            return super()._run_catalog_fallback(**kwargs)

    def _record_abandonment(
        self, search_id: str, source_id: str, elapsed: float, reason: str
    ) -> None:
        payload = {
            "source": source_id,
            "elapsed_seconds": round(elapsed, 3),
            "reason": reason,
        }
        append = getattr(self.controller.repos, "append_runtime_list", None)
        if callable(append):
            append(search_id, "abandoned_sources", payload)
            return
        runtime = self.controller.repos.get_runtime(search_id)
        abandoned = list(runtime.get("abandoned_sources") or [])
        abandoned.append(payload)
        self.controller.set_runtime(search_id, abandoned_sources=abandoned)

    def live_and_verify_all(
        self, search_id: str, candidates: list[ListingCandidate]
    ) -> list[ListingCandidate]:
        """One GET per listing: liveness and verification share the body."""
        if not candidates:
            return []
        from searcher.sources.adapters import resolve_adapter
        from searcher.sources.engine import _adapter_manifest
        from searcher.sources.live_check import classify_liveness
        from searcher.sources.statuses import classify_http
        from searcher.verification.runner import verify_candidate

        escalator = self._make_escalator(search_id)
        resolved: dict[str, tuple[Any, SourceManifest] | None] = {}

        def lookup(name: str) -> tuple[Any, SourceManifest] | None:
            if name not in resolved:
                try:
                    adapter = resolve_adapter(name)
                    resolved[name] = (adapter, _adapter_manifest(adapter))
                except Exception:
                    resolved[name] = None
            return resolved[name]

        def one(candidate: ListingCandidate) -> ListingCandidate:
            pair = lookup(candidate.source_adapter)
            if pair is None:
                return candidate
            adapter, manifest = pair
            doc = escalator.fetch(
                candidate.canonical_url,
                manifest,
                source_id=manifest.source_id,
                allow_render=True,
            )
            outcome = doc.result.outcome
            if outcome is SourceOutcome.SEARCHED_MATCHES_FOUND:
                outcome = classify_http(doc.result.http_status, body=doc.body)
            status = classify_liveness(
                http_status=doc.result.http_status,
                body=doc.body.decode("utf-8", errors="replace"),
                outcome=outcome,
            )
            fresh = candidate.model_copy(
                update={
                    "availability": status.availability,
                    "last_checked_at": status.checked_at,
                    "explanation": candidate.explanation.model_copy(
                        update={
                            "live_status": status.availability,
                            "last_checked_at": status.checked_at,
                        }
                    ),
                }
            )
            replay = _ReplayEscalator(doc)
            verified = verify_candidate(
                fresh,
                manifest,
                replay,  # type: ignore[arg-type]
                search_id=search_id,
                adapter=adapter,
                repos=self.repos,
            )
            self.repos.upsert_candidate(search_id, verified)
            return verified

        try:
            return map_by_host(
                candidates,
                one,
                host_of_item=lambda item: host_of(item.canonical_url) or item.canonical_url,
                cap_of=lambda item: _cap_for(lookup(item.source_adapter)),
            )
        except BudgetExceeded:
            listed = self.repos.list_candidates(search_id)
            by_id = {item.candidate_id: item for item in listed}
            return [by_id.get(item.candidate_id, item) for item in candidates]

    def live_check_all(
        self, search_id: str, candidates: list[ListingCandidate]
    ) -> list[ListingCandidate]:
        if not candidates:
            return []
        escalator = self._make_escalator(search_id)
        manifests: dict[str, tuple[Any, SourceManifest] | None] = {}

        def resolve(candidate: ListingCandidate) -> tuple[Any, SourceManifest] | None:
            name = candidate.source_adapter
            if name not in manifests:
                try:
                    from searcher.sources.adapters import resolve_adapter
                    from searcher.sources.engine import _adapter_manifest

                    adapter = resolve_adapter(name)
                    manifests[name] = (adapter, _adapter_manifest(adapter))
                except KeyError:
                    manifests[name] = None
            return manifests[name]

        def one(candidate: ListingCandidate) -> ListingCandidate:
            resolved = resolve(candidate)
            if resolved is None:
                return candidate
            _adapter, manifest = resolved
            fresh, _status = check_candidate(candidate, manifest, escalator)
            self.repos.upsert_candidate(search_id, fresh)
            return fresh

        try:
            return map_by_host(
                candidates,
                one,
                host_of_item=lambda item: host_of(item.canonical_url) or item.canonical_url,
                cap_of=lambda item: _cap_for(resolve(item)),
            )
        except BudgetExceeded:
            listed = self.repos.list_candidates(search_id)
            by_id = {item.candidate_id: item for item in listed}
            return [by_id.get(item.candidate_id, item) for item in candidates]

    def verify_all(
        self, search_id: str, candidates: list[ListingCandidate]
    ) -> list[ListingCandidate]:
        if not candidates:
            return []
        from searcher.sources.adapters import resolve_adapter
        from searcher.sources.engine import _adapter_manifest
        from searcher.verification.runner import verify_candidate

        escalator = self._make_escalator(search_id)
        resolved: dict[str, tuple[Any, SourceManifest] | None] = {}

        def lookup(name: str) -> tuple[Any, SourceManifest] | None:
            if name not in resolved:
                try:
                    adapter = resolve_adapter(name)
                    resolved[name] = (adapter, _adapter_manifest(adapter))
                except Exception:
                    resolved[name] = None
            return resolved[name]

        def one(candidate: ListingCandidate) -> ListingCandidate:
            pair = lookup(candidate.source_adapter)
            if pair is None:
                return candidate
            adapter, manifest = pair
            return verify_candidate(
                candidate,
                manifest,
                escalator,
                search_id=search_id,
                adapter=adapter,
                repos=self.repos,
            )

        try:
            return map_by_host(
                candidates,
                one,
                host_of_item=lambda item: host_of(item.canonical_url) or item.canonical_url,
                cap_of=lambda item: _cap_for(lookup(item.source_adapter)),
            )
        except BudgetExceeded:
            listed = self.repos.list_candidates(search_id)
            by_id = {item.candidate_id: item for item in listed}
            return [by_id.get(item.candidate_id, item) for item in candidates]


def _cap_for(resolved: tuple[Any, SourceManifest] | None) -> int:
    if resolved is None:
        return 1
    return concurrent_cap(resolved[1].rate_policy)


def install_bounded_discovery(
    *,
    source_deadline_seconds: float | None = None,
    request_timeout_seconds: float | None = None,
) -> None:
    """Point DiscoveryEngine at the deadline wrapper. Safe to call more than once."""
    import searcher.sources.engine as engine_mod

    if source_deadline_seconds is not None:
        BoundedDiscoveryEngine._default_source_deadline = source_deadline_seconds
    if request_timeout_seconds is not None:
        BoundedDiscoveryEngine._default_request_timeout = request_timeout_seconds
    engine_mod.DiscoveryEngine = BoundedDiscoveryEngine  # type: ignore[assignment,misc]
