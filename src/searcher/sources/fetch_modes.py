"""§15.3 cheap-first escalation. Browser is last resort and policy-gated."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from searcher.contracts.enums import FetchMode, SourceOutcome
from searcher.contracts.models import FetchAttempt, FetchResult, SourceManifest
from searcher.core.budgets import BudgetUsage
from searcher.core.errors import BudgetExceeded, CancelledError
from searcher.core.ids import new_id, sha256_hex
from searcher.core.time import utc_now
from searcher.normalization.url import canonicalize_url
from searcher.receipts.types import FetchRuntimeReceipt
from searcher.sources.admission import AdmissionGate
from searcher.sources.browser import BrowserPool, BrowserUnavailable
from searcher.sources.cache import ResponseCache
from searcher.sources.cancel import RunCancel
from searcher.sources.challenge import BLOCKED_BY_CHALLENGE, challenge_note, looks_like_challenge
from searcher.sources.fetch_log import FetchLog
from searcher.sources.http import HonestHttpClient, HttpResponse
from searcher.sources.rate_limit import BandwidthLimiter, HostLimiter
from searcher.sources.retry import backoff_seconds, parse_retry_after, should_retry
from searcher.sources.statuses import classify_http

REQUIRED_FIELDS = ("title", "url")


@dataclass
class FetchedDocument:
    result: FetchResult
    body: bytes
    headers: dict[str, str]
    final_url: str


class Escalator:
    def __init__(
        self,
        http: HonestHttpClient,
        admission: AdmissionGate,
        cache: ResponseCache | None,
        *,
        browsers: BrowserPool | None = None,
        host_limiter: HostLimiter | None = None,
        bandwidth: BandwidthLimiter | None = None,
        fetch_log: FetchLog | None = None,
        usage: BudgetUsage | None = None,
        cancel: RunCancel | None = None,
    ) -> None:
        self.http = http
        self.admission = admission
        self.cache = cache
        self.browsers = browsers
        self.host_limiter = host_limiter or HostLimiter()
        self.bandwidth = bandwidth
        self.fetch_log = fetch_log
        self.usage = usage
        self.cancel = cancel

    def fetch(
        self,
        url: str,
        manifest: SourceManifest,
        *,
        source_id: str,
        required_fields: list[str] | None = None,
        allow_render: bool = False,
        force_render: bool = False,
        skip_cache: bool = False,
        robots_body: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> FetchedDocument:
        if self.cancel is not None:
            self.cancel.raise_if_cancelled()
        purpose = "render" if force_render else "page_fetch"
        decision = self.admission.decide(
            url, manifest, purpose=purpose, robots_body=robots_body
        )
        if not decision.allowed:
            result = FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=decision.outcome,
                canonical_url=canonicalize_url(url),
                classification_note=decision.basis,
                mode=FetchMode.LIGHT_RENDER if force_render else FetchMode.HTTP,
            )
            return FetchedDocument(result=result, body=b"", headers={}, final_url=url)
        if force_render:
            return self.render(
                url, manifest, source_id=source_id, robots_body=robots_body, light=True
            )
        delay = (
            decision.crawl_delay
            if decision.crawl_delay is not None
            else 60.0 / max(manifest.rate_policy.requests_per_minute, 1)
        )
        cached = None if skip_cache or self.cache is None else self.cache.get(url)
        if cached is not None:
            result = FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=SourceOutcome.SEARCHED_MATCHES_FOUND,
                content_digest=cached.content_digest,
                bytes=len(cached.body),
                http_status=200,
                canonical_url=cached.url_canonical,
                mode=FetchMode.CACHE,
                content_type=cached.content_type,
                from_cache=True,
                final_url=url,
            )
            return FetchedDocument(
                result=result,
                body=cached.body,
                headers={"content-type": cached.content_type or ""},
                final_url=url,
            )
        if self.host_limiter is not None:
            self.host_limiter.wait(
                manifest.domain,
                rpm=manifest.rate_policy.requests_per_minute,
                burst=manifest.rate_policy.burst,
            )
        attempt = 1
        last_doc: FetchedDocument | None = None
        while True:
            if self.cancel is not None:
                self.cancel.raise_if_cancelled()
            started = utc_now()
            try:
                if self.usage is not None:
                    self.usage.consume(pages=1, bytes=0)
                response = self.http.get(url, base_delay=delay, extra_headers=extra_headers)
            except BudgetExceeded:
                raise
            except CancelledError:
                raise
            except Exception as exc:
                outcome = SourceOutcome.NETWORK_FAILED
                result = FetchResult(
                    attempt_id=new_id(),
                    url=url,
                    outcome=outcome,
                    canonical_url=canonicalize_url(url),
                    mode=FetchMode.HTTP,
                    error_class=type(exc).__name__,
                    classification_note=str(exc),
                )
                last_doc = FetchedDocument(result=result, body=b"", headers={}, final_url=url)
                if not should_retry(outcome, attempt):
                    self._log(source_id, url, result, started)
                    return last_doc
                time_sleep = backoff_seconds(attempt)
                import time

                time.sleep(time_sleep)
                attempt += 1
                continue
            outcome = classify_http(response.status, body=response.body)
            challenge = looks_like_challenge(response.text)
            if challenge:
                outcome = SourceOutcome.BLOCKED_BY_ACCESS
            if outcome is SourceOutcome.RATE_LIMITED:
                retry_after = parse_retry_after(response.headers.get("retry-after"))
            else:
                retry_after = None
            if self.usage is not None and response.body:
                try:
                    self.usage.consume(bytes=len(response.body))
                except BudgetExceeded:
                    outcome = SourceOutcome.UNMEASURABLE
            if self.bandwidth is not None:
                pause = self.bandwidth.charge(len(response.body))
                if pause > 0:
                    import time

                    time.sleep(pause)
            result = self._from_http(url, response, outcome)
            if challenge:
                result = result.model_copy(
                    update={
                        "classification_note": challenge_note(response.text),
                        "error_class": BLOCKED_BY_CHALLENGE,
                    }
                )
            self._log(source_id, url, result, started)
            last_doc = FetchedDocument(
                result=result,
                body=response.body,
                headers=response.headers,
                final_url=response.final_url,
            )
            if challenge:
                return last_doc
            if outcome is SourceOutcome.SEARCHED_MATCHES_FOUND:
                if self.cache is not None and response.status == 200:
                    self.cache.put(
                        response.final_url or url,
                        response.body,
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        content_type=response.content_type,
                    )
                if allow_render and self._needs_render(
                    response, required_fields or list(REQUIRED_FIELDS)
                ):
                    rendered = self.render(
                        url, manifest, source_id=source_id, robots_body=robots_body
                    )
                    if self._prefer_rendered(rendered):
                        return rendered
                return last_doc
            if should_retry(outcome, attempt):
                import time

                time.sleep(min(5.0, backoff_seconds(attempt, retry_after)))
                attempt += 1
                continue
            return last_doc

    def _prefer_rendered(self, rendered: FetchedDocument) -> bool:
        """Keep the HTTP body when the renderer never actually ran."""
        note = rendered.result.classification_note or ""
        if note in {"browser extra unavailable", "browser budget exhausted"}:
            return False
        if rendered.result.error_class == "BROWSER":
            return False
        if (
            rendered.result.outcome is SourceOutcome.NETWORK_FAILED
            and not rendered.body
        ):
            return False
        return rendered.result.mode in {FetchMode.LIGHT_RENDER, FetchMode.BROWSER}

    def _needs_render(self, response: HttpResponse, required: list[str]) -> bool:
        text = response.text.lower()
        if len(response.body) < 400 and "html" in (response.content_type or ""):
            return True
        if "enable javascript" in text or "noscript" in text and len(response.body) < 2000:
            return True
        del required
        return False

    def render(
        self,
        url: str,
        manifest: SourceManifest,
        *,
        source_id: str,
        robots_body: str | None = None,
        light: bool = True,
    ) -> FetchedDocument:
        """Browser-rendered GET. Admission → robots → rate → budget → one fetch.

        A challenge is terminal. There is no retry loop and no stealth.
        """
        if self.cancel is not None:
            self.cancel.raise_if_cancelled()
        started = utc_now()
        mode = FetchMode.LIGHT_RENDER if light else FetchMode.BROWSER
        decision = self.admission.decide(
            url, manifest, purpose="render", robots_body=robots_body
        )
        if not decision.allowed:
            result = FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=decision.outcome,
                canonical_url=canonicalize_url(url),
                classification_note=decision.basis,
                mode=mode,
            )
            self._log(source_id, url, result, started)
            return FetchedDocument(result=result, body=b"", headers={}, final_url=url)
        if self.browsers is None:
            result = FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=SourceOutcome.UNMEASURABLE,
                canonical_url=canonicalize_url(url),
                classification_note="browser extra unavailable",
                mode=mode,
            )
            self._log(source_id, url, result, started)
            return FetchedDocument(result=result, body=b"", headers={}, final_url=url)
        if self.host_limiter is not None:
            self.host_limiter.wait(
                manifest.domain,
                rpm=manifest.rate_policy.requests_per_minute,
                burst=manifest.rate_policy.burst,
            )
        if self.usage is not None:
            try:
                self.usage.consume(browser_pages=1)
            except BudgetExceeded:
                result = FetchResult(
                    attempt_id=new_id(),
                    url=url,
                    outcome=SourceOutcome.UNMEASURABLE,
                    canonical_url=canonicalize_url(url),
                    classification_note="browser budget exhausted",
                    mode=mode,
                    error_class="BUDGET",
                )
                self._log(source_id, url, result, started)
                return FetchedDocument(result=result, body=b"", headers={}, final_url=url)
        try:
            with self.browsers.page(url, light=light) as lease:
                body = lease.content.encode("utf-8")
                text = lease.content
                challenge = looks_like_challenge(text)
                outcome = classify_http(lease.status, body=body, challenge=challenge)
                note = challenge_note(text) if challenge else None
                if self.usage is not None and body:
                    try:
                        self.usage.consume(bytes=len(body))
                    except BudgetExceeded:
                        outcome = SourceOutcome.UNMEASURABLE
                result = FetchResult(
                    attempt_id=new_id(),
                    url=url,
                    outcome=outcome,
                    content_digest=sha256_hex(body),
                    bytes=len(body),
                    http_status=lease.status,
                    canonical_url=canonicalize_url(lease.final_url or url),
                    mode=mode,
                    final_url=lease.final_url,
                    classification_note=note,
                    error_class=BLOCKED_BY_CHALLENGE if challenge else None,
                )
                self._log(source_id, url, result, started)
                return FetchedDocument(
                    result=result,
                    body=body,
                    headers={},
                    final_url=lease.final_url,
                )
        except BrowserUnavailable as exc:
            result = FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=SourceOutcome.UNMEASURABLE,
                canonical_url=canonicalize_url(url),
                classification_note=str(exc),
                mode=mode,
                error_class="BROWSER",
            )
            self._log(source_id, url, result, started)
            return FetchedDocument(result=result, body=b"", headers={}, final_url=url)
        except Exception as exc:
            result = FetchResult(
                attempt_id=new_id(),
                url=url,
                outcome=SourceOutcome.NETWORK_FAILED,
                canonical_url=canonicalize_url(url),
                classification_note=str(exc),
                mode=mode,
                error_class=type(exc).__name__,
            )
            self._log(source_id, url, result, started)
            return FetchedDocument(result=result, body=b"", headers={}, final_url=url)

    def _render(
        self,
        url: str,
        manifest: SourceManifest,
        source_id: str,
        *,
        light: bool,
    ) -> FetchedDocument | None:
        rendered = self.render(url, manifest, source_id=source_id, light=light)
        if rendered.result.mode in {FetchMode.LIGHT_RENDER, FetchMode.BROWSER}:
            if rendered.result.outcome is SourceOutcome.UNMEASURABLE:
                return None
            return rendered
        return None

    def _from_http(self, url: str, response: HttpResponse, outcome: SourceOutcome) -> FetchResult:
        return FetchResult(
            attempt_id=new_id(),
            url=url,
            outcome=outcome,
            content_digest=response.digest if response.body else None,
            bytes=len(response.body),
            http_status=response.status,
            canonical_url=canonicalize_url(response.final_url or url),
            mode=FetchMode.HTTP,
            content_type=response.content_type,
            retry_after_seconds=parse_retry_after(response.headers.get("retry-after")),
            redirected_from=response.redirected_from,
            final_url=response.final_url,
        )

    def _log(self, source_id: str, url: str, result: FetchResult, started: Any) -> None:
        if self.fetch_log is None:
            return
        attempt = FetchAttempt(
            attempt_id=result.attempt_id,
            source_id=source_id,
            url=url,
            canonical_url=result.canonical_url or canonicalize_url(url),
            started_at=started,
            ended_at=utc_now(),
            mode=result.mode,
            status=result.outcome,
            http_status=result.http_status,
            content_digest=result.content_digest,
            bytes=result.bytes,
            error_class=result.error_class,
        )
        self.fetch_log.append(attempt)

    def runtime_receipt(
        self, search_id: str, source_id: str, doc: FetchedDocument
    ) -> FetchRuntimeReceipt:  # noqa: E501
        return FetchRuntimeReceipt(
            search_id=search_id,
            url=doc.result.url,
            mode=doc.result.mode.value,
            outcome=doc.result.outcome.value,
            http_status=doc.result.http_status,
            bytes=doc.result.bytes,
            cache_hit=doc.result.from_cache,
            duration_ms=0,
            source_id=source_id,
        ).seal()


# Extraction-plan name.
escalate = Escalator
