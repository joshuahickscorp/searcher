"""A source asked for and then skipped is reported, not dropped."""

from __future__ import annotations

import pytest
from tests.conftest import make_intent

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import (
    QueryType,
    SourceAdmission,
    SourceHealthState,
    SourceOutcome,
)
from searcher.contracts.models import QueryVariant, SourceHealth, SourceManifest
from searcher.core.budgets import Budget
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.sources.broker import Coverage, SourceBroker
from searcher.sources.engine import DiscoveryEngine


def _query(language: str = "en") -> QueryVariant:
    return QueryVariant(
        query_id=new_id(),
        hypothesis_id="h",
        round=1,
        language=language,
        query_text="dior homme trainer",
        query_type=QueryType.EXACT_NAME,
        expected_gain=0.5,
    )


def _manifest(**overrides: object) -> SourceManifest:
    payload: dict[str, object] = {
        "source_id": "shop",
        "adapter": "shop",
        "domain": "shop.example",
        "access_method": "http_get",
        "admission_status": SourceAdmission.ADMITTED,
        "allowed_use": "test",
        "source_class": "resale",
        "languages": ["en"],
        "enabled": True,
        "authentication": "none",
    }
    payload.update(overrides)
    return SourceManifest.model_validate(payload)


def _broker(
    manifests: dict[str, SourceManifest] | None = None,
    *,
    names: tuple[str, ...] | None = None,
    health: object | None = None,
) -> SourceBroker:
    held = manifests or {}
    broker = SourceBroker(
        health=health,  # type: ignore[arg-type]
        names=names if names is not None else tuple(held),
    )

    def manifest_of(name: str) -> SourceManifest:
        if name not in held:
            raise KeyError(name)
        return held[name]

    broker.manifest_of = manifest_of  # type: ignore[method-assign]
    return broker


def _assert_skip(coverage: Coverage, source_id: str, outcome: SourceOutcome) -> None:
    assert source_id in coverage.per_source, coverage.per_source
    assert coverage.per_source[source_id] == outcome.value
    assert coverage.per_source[source_id] != SourceOutcome.SEARCHED_NO_MATCH.value
    assert coverage.per_source[source_id] != SourceOutcome.SEARCHED_MATCHES_FOUND.value


def test_named_credential_source_is_auth_required_not_absent() -> None:
    broker = _broker({"ebay": _manifest(source_id="ebay", authentication="oauth")})
    plans = broker.plan([_query()])
    assert plans == []
    _assert_skip(broker.coverage, "ebay", SourceOutcome.AUTH_REQUIRED)


def test_skips_land_on_the_coverage_map_passed_in() -> None:
    coverage = Coverage()
    broker = _broker({"ebay": _manifest(source_id="ebay", authentication="oauth")})
    broker.plan([_query()], coverage=coverage)
    _assert_skip(coverage, "ebay", SourceOutcome.AUTH_REQUIRED)


@pytest.mark.parametrize(
    ("name", "manifests", "kwargs", "outcome"),
    [
        (
            "ghost",
            {},
            {"names": ("ghost",)},
            SourceOutcome.UNMEASURABLE,
        ),
        (
            "shop",
            {"shop": _manifest(source_id="shop")},
            {"families": frozenset({"replica"})},
            SourceOutcome.NOT_ATTEMPTED,
        ),
        (
            "depop",
            {"depop": _manifest(source_id="depop", enabled=False)},
            {},
            SourceOutcome.BLOCKED_BY_POLICY,
        ),
        (
            "blocked_shop",
            {
                "blocked_shop": _manifest(
                    source_id="blocked_shop",
                    admission_status=SourceAdmission.BLOCKED,
                )
            },
            {},
            SourceOutcome.BLOCKED_BY_POLICY,
        ),
        (
            "ko_shop",
            {
                "ko_shop": _manifest(
                    source_id="ko_shop",
                    languages=["ko"],
                    source_class="resale",
                )
            },
            {},
            SourceOutcome.NOT_ATTEMPTED,
        ),
    ],
)
def test_each_other_skip_reason_is_reported(
    name: str,
    manifests: dict[str, SourceManifest],
    kwargs: dict[str, object],
    outcome: SourceOutcome,
) -> None:
    options = dict(kwargs)
    broker = _broker(manifests, names=options.pop("names", None))
    plans = broker.plan([_query()], **options)  # type: ignore[arg-type]
    assert name not in {plan.source_adapter for plan in plans}
    _assert_skip(broker.coverage, name, outcome)


def test_health_forbids_planning_is_reported() -> None:
    record = SourceHealth(
        source_id="kind",
        last_outcome=SourceOutcome.BLOCKED_BY_ACCESS,
        last_checked_at=utc_now(),
        state=SourceHealthState.BLOCKED,
    )

    class _Health:
        def get(self, source_id: str) -> SourceHealth | None:
            return record if source_id == "kind" else None

    broker = _broker({"kind": _manifest(source_id="kind")}, health=_Health())
    plans = broker.plan([_query()])
    assert plans == []
    _assert_skip(broker.coverage, "kind", SourceOutcome.BLOCKED_BY_ACCESS)


def test_planned_source_is_not_recorded_as_a_skip() -> None:
    broker = _broker({"kind": _manifest(source_id="kind")})
    plans = broker.plan([_query()])
    assert [plan.source_adapter for plan in plans] == ["kind"]
    assert "kind" not in broker.coverage.per_source


def test_engine_run_reports_explicit_ebay_as_auth_required(
    controller: CampaignController,
) -> None:
    intent = make_intent()
    controller.create(intent, budget=Budget.fixture_default())
    query = _query()
    controller.repos.upsert_query(intent.search_id, query)
    engine = DiscoveryEngine(controller)
    try:
        summary = engine.run(intent.search_id, [query], source_names=["ebay"])
    finally:
        engine.close()
    assert "ebay" in summary.coverage
    assert summary.coverage["ebay"] == SourceOutcome.AUTH_REQUIRED.value
    assert summary.coverage["ebay"] != SourceOutcome.SEARCHED_NO_MATCH.value
