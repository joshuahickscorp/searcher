"""Admission is recorded policy plus a live robots.txt check for the exact path."""

from __future__ import annotations

from dataclasses import dataclass

from searcher.contracts.enums import SourceAdmission, SourceOutcome
from searcher.contracts.models import SourceManifest
from searcher.core.config import HONEST_USER_AGENT
from searcher.core.errors import SsrfBlocked
from searcher.security.ssrf import assert_url_safe
from searcher.sources.http import HonestHttpClient, origin_of
from searcher.sources.policy import SourcePolicy, policy_from_manifest
from searcher.sources.robots import RobotsBlocked, RobotsCache, path_matches_prefix


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    allowed: bool
    outcome: SourceOutcome
    basis: str
    robots_allowed: bool | None = None
    crawl_delay: float | None = None


class AdmissionGate:
    def __init__(
        self,
        robots: RobotsCache,
        http: HonestHttpClient,
        *,
        user_agent: str = HONEST_USER_AGENT,
    ) -> None:
        self.robots = robots
        self.http = http
        self.user_agent = user_agent

    def decide(
        self,
        url: str,
        manifest: SourceManifest,
        *,
        purpose: str = "page_fetch",
        policy: SourcePolicy | None = None,
        skip_live_robots: bool = False,
        robots_body: str | None = None,
    ) -> AdmissionDecision:
        recorded = policy or policy_from_manifest(manifest)
        if not manifest.enabled:
            return AdmissionDecision(
                False,
                SourceOutcome.BLOCKED_BY_POLICY,
                "adapter disabled by default"
                + (f": {manifest.open_question}" if manifest.open_question else ""),  # noqa: E501
            )
        if manifest.admission_status is SourceAdmission.BLOCKED:
            return AdmissionDecision(
                False,
                SourceOutcome.BLOCKED_BY_POLICY,
                f"source {manifest.source_id} is recorded blocked",
            )
        if purpose == "search" and not recorded.search:
            return AdmissionDecision(
                False,
                SourceOutcome.BLOCKED_BY_POLICY,
                f"search is not an admitted use of {manifest.source_id}",
            )
        if purpose == "render" and not recorded.render:
            return AdmissionDecision(
                False,
                SourceOutcome.BLOCKED_BY_POLICY,
                f"render is not an admitted use of {manifest.source_id}",
            )
        api_methods = {"official_api", "self_hosted_api", "action_api"}
        if (
            purpose == "page_fetch"
            and not recorded.page_fetch
            and manifest.access_method not in api_methods
        ):
            return AdmissionDecision(
                False,
                SourceOutcome.BLOCKED_BY_POLICY,
                f"page fetch is not an admitted use of {manifest.source_id}",
            )
        try:
            assert_url_safe(url, resolve=True)
        except SsrfBlocked as exc:
            return AdmissionDecision(False, SourceOutcome.BLOCKED_BY_POLICY, str(exc))
        if path_matches_prefix(url, list(manifest.disallowed_path_prefixes)):
            return AdmissionDecision(
                False,
                SourceOutcome.BLOCKED_BY_POLICY,
                f"recorded disallowed path prefix for {manifest.source_id}",
            )
        if skip_live_robots:
            return AdmissionDecision(True, SourceOutcome.NOT_ATTEMPTED, "live robots skipped", True)
        snapshot_body = robots_body
        origin = origin_of(url)
        if snapshot_body is None:
            cached = self.robots.get_cached(origin)
            if cached is not None:
                if cached.status == "fetch_failed":
                    return AdmissionDecision(
                        False,
                        SourceOutcome.BLOCKED_BY_POLICY,
                        "robots.txt fetch previously failed; fail-closed",
                        False,
                    )
                snapshot_body = cached.body
                crawl = cached.crawl_delay
                allowed = self.robots.allows(url, snapshot_body)
                if not allowed:
                    return AdmissionDecision(
                        False,
                        SourceOutcome.BLOCKED_BY_POLICY,
                        "robots.txt disallows this path",
                        False,
                        crawl,
                    )
                return AdmissionDecision(
                    True, SourceOutcome.NOT_ATTEMPTED, "robots allow", True, crawl
                )  # noqa: E501
            snapshot_body, fetch_status = self._fetch_robots(origin)
            if fetch_status != "ok":
                self.robots.remember_failure(origin)
                return AdmissionDecision(
                    False,
                    SourceOutcome.BLOCKED_BY_POLICY,
                    "robots.txt fetch failed; treated as disallowed",
                    False,
                )
        snapshot = self.robots.parse_body(origin, snapshot_body, status="ok")
        self.robots.store(snapshot)
        allowed = self.robots.allows(url, snapshot_body)
        if not allowed:
            return AdmissionDecision(
                False,
                SourceOutcome.BLOCKED_BY_POLICY,
                "robots.txt disallows this path",
                False,
                snapshot.crawl_delay,
            )
        return AdmissionDecision(
            True,
            SourceOutcome.NOT_ATTEMPTED,
            "recorded policy + live robots allow",
            True,
            snapshot.crawl_delay,
        )

    def _fetch_robots(self, origin: str) -> tuple[str, str]:
        robots_url = f"{origin}/robots.txt"
        try:
            assert_url_safe(robots_url, resolve=True)
            response = self.http.get(robots_url, base_delay=0.2, pace=True)
        except Exception:
            return "", "fetch_failed"
        if response.status >= 500:
            return "", "fetch_failed"
        if response.status == 404:
            # A 404 robots.txt is an empty allow file (we successfully asked).
            return "", "ok"
        if response.status != 200:
            return "", "fetch_failed"
        return response.text, "ok"

    def refuse_if_disallowed(
        self, url: str, manifest: SourceManifest, **kwargs: object
    ) -> AdmissionDecision:  # noqa: E501
        decision = self.decide(url, manifest, **kwargs)  # type: ignore[arg-type]
        if not decision.allowed:
            raise RobotsBlocked(url, decision.basis)
        return decision
