"""§14.1 source broker: choose sources per query, respect budgets, record coverage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from searcher.contracts.enums import SourceAdmission, SourceHealthState, SourceOutcome
from searcher.contracts.models import Admission, QueryVariant, SourceManifest, SourcePlan
from searcher.core.budgets import BudgetUsage
from searcher.core.ids import new_id
from searcher.sources.adapters import resolve_adapter
from searcher.sources.families import family_for
from searcher.sources.health import HealthStore, may_plan
from searcher.sources.platform import requires_operator_credential
from searcher.sources.policy import policy_for

DEFAULT_ORDER = (
    "searx",
    "wikimedia",
    "marginalia",
    "the_realreal",
    "rebag",
    "komehyo",
    "kind",
    "byronesque",
    "heroine",
    "archive_org",
    "ebay",
    "etsy",
    "mercari_jp",
    "yahoo_auctions",
    "buyee",
    "vinted",
    "bunjang",
    "ssense",
    "depop",
    "grailed",
    "vestiaire",
    "taobao",
    "weidian",
    "yupoo",
)


@dataclass
class Coverage:
    per_source: dict[str, str] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)
    strategies: dict[str, list[dict[str, object]]] = field(default_factory=dict)

    def record(
        self,
        source_id: str,
        outcome: SourceOutcome,
        *,
        detail: str = "",
        strategies: list[dict[str, object]] | None = None,
    ) -> None:
        self.per_source[source_id] = outcome.value
        if detail:
            self.details[source_id] = detail
        if strategies is not None:
            self.strategies[source_id] = list(strategies)


def _health_skip_outcome(record: object) -> SourceOutcome:
    last = getattr(record, "last_outcome", None)
    if isinstance(last, SourceOutcome) and last not in {
        SourceOutcome.SEARCHED_MATCHES_FOUND,
        SourceOutcome.SEARCHED_NO_MATCH,
        SourceOutcome.NOT_ATTEMPTED,
    }:
        return last
    state = getattr(record, "state", None)
    if state is SourceHealthState.POLICY_DISABLED:
        return SourceOutcome.BLOCKED_BY_POLICY
    if state is SourceHealthState.UNAVAILABLE:
        return SourceOutcome.SOURCE_UNAVAILABLE
    return SourceOutcome.BLOCKED_BY_ACCESS


class SourceBroker:
    def __init__(
        self,
        *,
        health: HealthStore | None = None,
        names: tuple[str, ...] = DEFAULT_ORDER,
    ) -> None:
        self.health = health
        self.names = names
        self.coverage = Coverage()

    def manifest_of(self, name: str) -> SourceManifest:
        adapter = resolve_adapter(name)
        result = cast(Any, adapter).manifest()
        if not isinstance(result, SourceManifest):
            raise TypeError(f"{name} manifest() did not return SourceManifest")
        return result

    def plan(
        self,
        queries: list[QueryVariant],
        usage: BudgetUsage | None = None,
        *,
        include_disabled: bool = False,
        families: frozenset[str] | None = None,
        coverage: Coverage | None = None,
    ) -> list[SourcePlan]:
        if coverage is None:
            coverage = Coverage()
        self.coverage = coverage
        languages = {query.language for query in queries}
        query_ids = [query.query_id for query in queries]
        plans: list[SourcePlan] = []
        for name in self.names:
            try:
                manifest = self.manifest_of(name)
            except Exception as exc:
                coverage.record(
                    name,
                    SourceOutcome.UNMEASURABLE,
                    detail=f"manifest lookup failed: {type(exc).__name__}",
                )
                continue
            source_id = manifest.source_id
            if families is not None and family_for(source_id).value not in families:
                coverage.record(
                    source_id, SourceOutcome.NOT_ATTEMPTED, detail="family not selected"
                )
                continue
            if not include_disabled and not manifest.enabled:
                coverage.record(
                    source_id, SourceOutcome.BLOCKED_BY_POLICY, detail="source disabled"
                )
                continue
            if not include_disabled and requires_operator_credential(manifest):
                coverage.record(
                    source_id,
                    SourceOutcome.AUTH_REQUIRED,
                    detail="operator credential required",
                )
                continue
            if manifest.admission_status is SourceAdmission.BLOCKED:
                coverage.record(
                    source_id,
                    SourceOutcome.BLOCKED_BY_POLICY,
                    detail="source admission blocked",
                )
                continue
            overlap = languages & set(manifest.languages)
            lang_ok = not languages or not manifest.languages or bool(overlap)
            general = manifest.source_class in {"metasearch", "general_web", "reference"}
            if not lang_ok and "en" not in manifest.languages and not general:
                coverage.record(source_id, SourceOutcome.NOT_ATTEMPTED, detail="language mismatch")
                continue
            if self.health is not None:
                record = self.health.get(source_id)
                if record is not None and not may_plan(record.state):
                    coverage.record(
                        source_id,
                        _health_skip_outcome(record),
                        detail=f"health forbids planning ({record.state})",
                    )
                    continue
            recorded = policy_for(manifest.source_id)
            basis = recorded.notes if recorded else manifest.robots_policy
            if usage is not None and usage.would_exceed(sources=1) is not None:
                break
            plans.append(
                SourcePlan(
                    source_plan_id=new_id(),
                    source_adapter=manifest.source_id,
                    query_ids=query_ids,
                    admission=Admission(
                        status=manifest.admission_status, basis=basis or "recorded"
                    ),  # noqa: E501
                    rate_policy=manifest.rate_policy,
                    auth_mode=manifest.authentication,
                    fetch_modes=list(manifest.fetch_modes),
                    expected_fields=list(manifest.fields),
                )
            )
        return plans
