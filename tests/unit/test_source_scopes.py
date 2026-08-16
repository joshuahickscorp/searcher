"""Source scopes select families. Absent field matches today's planner."""

from __future__ import annotations

from searcher.contracts.enums import QueryType, SourceAdmission, SourceFamily
from searcher.contracts.models import QueryVariant
from searcher.core.ids import new_id
from searcher.sources.adapters import ADAPTER_REGISTRY, resolve_adapter
from searcher.sources.broker import DEFAULT_ORDER, SourceBroker
from searcher.sources.families import (
    family_for,
    names_for_scopes,
    normalize_source_scopes,
    registered_ids_for,
)


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


def test_absent_and_unknown_scopes_default_to_legitimate() -> None:
    assert normalize_source_scopes(None) == ("legitimate",)
    assert normalize_source_scopes([]) == ("legitimate",)
    assert normalize_source_scopes(["nope", "also-nope"]) == ("legitimate",)
    assert normalize_source_scopes(["replica", "bogus", "replica"]) == ("replica",)
    assert normalize_source_scopes(["legitimate", "replica", "mystery"]) == (
        "legitimate",
        "replica",
    )


def test_absent_scopes_plan_the_same_sources_as_today() -> None:
    query = _query()
    today = {plan.source_adapter for plan in SourceBroker().plan([query])}
    scoped = {
        plan.source_adapter
        for plan in SourceBroker().plan([query], families=frozenset({"legitimate"}))
    }
    assert today == scoped
    assert today
    for name in today:
        assert family_for(name) is SourceFamily.LEGITIMATE
    for name in ("taobao", "weidian", "yupoo"):
        assert name not in today


def test_legitimate_scope_plans_only_legitimate_family() -> None:
    plans = SourceBroker().plan(
        [_query()],
        include_disabled=True,
        families=frozenset({"legitimate"}),
    )
    adapters = {plan.source_adapter for plan in plans}
    assert "ebay" in adapters
    assert "the_realreal" in adapters
    assert "ssense" in adapters
    assert "depop" in adapters
    assert "grailed" in adapters
    assert "vestiaire" in adapters
    for name in adapters:
        assert family_for(name) is SourceFamily.LEGITIMATE
    for name in ("taobao", "weidian", "yupoo"):
        assert name not in adapters


def test_replica_scope_plans_only_replica_family() -> None:
    plans = SourceBroker().plan(
        [_query()],
        include_disabled=True,
        families=frozenset({"replica"}),
    )
    adapters = {plan.source_adapter for plan in plans}
    assert adapters == {"taobao", "weidian", "yupoo"}
    for name in ("ebay", "ssense", "depop", "searx"):
        assert name not in adapters


def test_both_scopes_plan_both_families() -> None:
    plans = SourceBroker().plan(
        [_query()],
        include_disabled=True,
        families=frozenset({"legitimate", "replica"}),
    )
    adapters = {plan.source_adapter for plan in plans}
    assert "ebay" in adapters
    assert "taobao" in adapters
    assert "yupoo" in adapters
    assert family_for("taobao") is SourceFamily.REPLICA
    assert family_for("ebay") is SourceFamily.LEGITIMATE


def test_unknown_scope_values_do_not_change_planning() -> None:
    names = names_for_scopes(
        ["nope", "also-nope"],
        None,
        default_order=DEFAULT_ORDER,
    )
    legit = names_for_scopes(["legitimate"], None, default_order=DEFAULT_ORDER)
    assert names == legit
    assert "taobao" not in names


def test_replica_sources_are_registered_disabled_pending_review() -> None:
    for name in ("depop", "grailed", "vestiaire", "taobao", "weidian", "yupoo"):
        manifest = resolve_adapter(name).manifest()  # type: ignore[attr-defined]
        assert manifest.enabled is False
        assert manifest.admission_status is SourceAdmission.REVIEW_REQUIRED
        assert manifest.open_question
        page = resolve_adapter(name).discover(_query(), None)  # type: ignore[attr-defined]
        assert page.outcome == "BLOCKED_BY_POLICY"


def test_dhgate_is_not_registered() -> None:
    assert "dhgate" not in ADAPTER_REGISTRY
    assert "dhgate" not in DEFAULT_ORDER
    assert "dhgate" not in registered_ids_for(SourceFamily.REPLICA)
    assert "dhgate" not in registered_ids_for(SourceFamily.LEGITIMATE)


def test_new_pending_adapters_never_fetch() -> None:
    adapter = resolve_adapter("yupoo")
    fetched = adapter.fetch("https://yupoo.com/album", "http")  # type: ignore[attr-defined]
    assert fetched.result.outcome.value == "BLOCKED_BY_POLICY"
    assert fetched.body == b""
