"""Campaign-entry deadlines around the discovery engine.

The HTTP client, escalator, and engine live in a lane this worker may not
edit. Those layers retry a timed-out fetch up to four times with backoff
and walk sources one by one with no per-source ceiling, so a single silent
host holds DISCOVERING at "Searching international sources" for ~90s.

This wrapper is the worker's deadline: each source gets a wall budget,
each request is capped to the remaining time, retries stop when the budget
is gone, and a stall is recorded as SOURCE_UNAVAILABLE with the elapsed
time. Per-host crawl-delay and rpm are still honoured — the wrapper never
goes faster than the declared rate, it just refuses to wait past the
source deadline.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx

from searcher.contracts.enums import FetchMode, SourceOutcome
from searcher.contracts.models import FetchResult, QueryVariant, SourceManifest, SourcePlan
from searcher.core.deadlines import (
    RETRY_REMAINING_FLOOR_SECONDS,
    connect_timeout_seconds,
    default_request_timeout,
    default_source_deadline,
)
from searcher.core.errors import ErrorClass
from searcher.core.ids import new_id
from searcher.sources.engine import DiscoveryEngine
from searcher.sources.events import SourceEvents
from searcher.sources.fetch_modes import Escalator, FetchedDocument
from searcher.sources.http import FetchError, HonestHttpClient

DEADLINE_REASON = "source deadline exceeded"


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
        self._deadline_at: float | None = None
        self.deadline_tripped = False
        self._apply_timeout(float(self.timeout), self.connect_timeout)

    def set_deadline(self, when: float | None) -> None:
        self._deadline_at = when

    def clear_deadline(self) -> None:
        self._deadline_at = None

    def remaining(self) -> float | None:
        if self._deadline_at is None:
            return None
        return self._deadline_at - time.monotonic()

    def _apply_timeout(self, total: float, connect: float) -> None:
        self._client.timeout = httpx.Timeout(total, connect=min(connect, total))

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
            self.limiter_for(url, base_delay).last_at = time.monotonic()
        if remaining is not None:
            cap = max(RETRY_REMAINING_FLOOR_SECONDS, min(float(self.timeout), remaining))
            self._apply_timeout(cap, min(self.connect_timeout, cap))
        try:
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
        finally:
            self._apply_timeout(float(self.timeout), self.connect_timeout)

    def _pace_wait(self, url: str, base_delay: float) -> float:
        limiter = self.limiter_for(url, base_delay)
        with limiter.lock:
            elapsed = time.monotonic() - limiter.last_at
            jittered = limiter.base_delay * random.uniform(0.7, 1.3)
            if elapsed >= jittered:
                return 0.0
            return jittered - elapsed


@contextmanager
def _bound_retries(remaining_fn: Callable[[], float]) -> Iterator[None]:
    import searcher.sources.fetch_modes as fetch_modes

    orig_retry = fetch_modes.should_retry  # type: ignore[attr-defined]
    orig_backoff = fetch_modes.backoff_seconds  # type: ignore[attr-defined]

    def gated_retry(outcome: SourceOutcome, attempt: int, **kwargs: Any) -> bool:
        if remaining_fn() <= RETRY_REMAINING_FLOOR_SECONDS:
            return False
        return bool(orig_retry(outcome, attempt, **kwargs))

    def gated_backoff(attempt: int, retry_after: float | None = None) -> float:
        delay = float(orig_backoff(attempt, retry_after))
        left = remaining_fn()
        if left <= 0:
            return 0.0
        return min(delay, left)

    fetch_modes.should_retry = gated_retry  # type: ignore[attr-defined]
    fetch_modes.backoff_seconds = gated_backoff  # type: ignore[attr-defined]
    try:
        yield
    finally:
        fetch_modes.should_retry = orig_retry  # type: ignore[attr-defined]
        fetch_modes.backoff_seconds = orig_backoff  # type: ignore[attr-defined]


class _SingleLimiterEscalator(Escalator):
    """Drop the extra token bucket. HTTP already paces crawl-delay / rpm."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "host_limiter", None)


class BoundedDiscoveryEngine(DiscoveryEngine):
    """DiscoveryEngine with a per-source wall deadline and request budgets."""

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
        self._deadline_at: float | None = None
        self._cut_short = False
        if http is None:
            http = DeadlineHttpClient(timeout=self.request_timeout_seconds)
        super().__init__(controller, http=http, batch_size=batch_size, max_work=max_work)

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
        self._deadline_at = deadline_at
        setter = getattr(self.http, "set_deadline", None)
        if callable(setter):
            setter(deadline_at)
        import searcher.sources.engine as engine_mod

        previous = getattr(engine_mod, "Escalator", Escalator)
        engine_mod.Escalator = _SingleLimiterEscalator  # type: ignore[attr-defined]
        elapsed = 0.0
        try:
            with _bound_retries(lambda: deadline_at - time.monotonic()):
                result = super()._run_plan(search_id, plan, queries, events, cancel)
        finally:
            engine_mod.Escalator = previous  # type: ignore[attr-defined]
            clearer = getattr(self.http, "clear_deadline", None)
            if callable(clearer):
                clearer()
            elapsed = time.monotonic() - started
            self._deadline_at = None
        tripped = self._cut_short or bool(getattr(self.http, "deadline_tripped", False))
        if tripped:
            reason = f"{DEADLINE_REASON} after {elapsed:.2f}s"
            events.blocked(plan.source_adapter, SourceOutcome.SOURCE_UNAVAILABLE.value, reason)
            self._record_abandonment(search_id, plan.source_adapter, elapsed, reason)
        if hasattr(self.http, "deadline_tripped"):
            self.http.deadline_tripped = False
        self._cut_short = False
        return result

    def _fetch_item(
        self,
        adapter: Any,
        escalator: Escalator,
        url: str,
        manifest: SourceManifest,
    ) -> FetchedDocument:
        if self._deadline_at is not None and self._deadline_at - time.monotonic() <= 0:
            self._cut_short = True
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

    def _record_abandonment(
        self, search_id: str, source_id: str, elapsed: float, reason: str
    ) -> None:
        runtime = self.controller.repos.get_runtime(search_id)
        abandoned = list(runtime.get("abandoned_sources") or [])
        abandoned.append(
            {
                "source": source_id,
                "elapsed_seconds": round(elapsed, 3),
                "reason": reason,
            }
        )
        self.controller.set_runtime(search_id, abandoned_sources=abandoned)


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
    engine_mod.DiscoveryEngine = BoundedDiscoveryEngine  # type: ignore[misc]
