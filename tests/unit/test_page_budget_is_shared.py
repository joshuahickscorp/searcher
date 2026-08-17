"""One source must not spend the campaign page budget on its catalogue walk.

A live footwear campaign at 2986d11 fetched 64 catalogue pages on a campaign
budgeted 40. rebag completed; the other eight answerable sources were
UNMEASURABLE because `usage.consume` failed before they ran. `kind`, which
held the item, was among them.

`page_catalog` was called without `caps`, so it used DEFAULT_PAGES_PER_SOURCE
(64) and DEFAULT_PAGES_PER_CAMPAIGN (80). The campaign's page_limit never
entered the walk.

Share formula: max(FLOOR, remaining_pages // N) with FLOOR = 2.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from tests.conftest import make_intent

from searcher.contracts.enums import QueryType, SourceAdmission, SourceOutcome
from searcher.contracts.models import Admission, QueryVariant, SourcePlan
from searcher.core.budgets import Budget
from searcher.core.errors import BudgetExceeded
from searcher.core.ids import new_id
from searcher.sources.engine import (
    CATALOG_PAGE_SHARE_FLOOR,
    catalog_caps_for_campaign,
    catalog_page_share,
    remaining_page_budget,
)
from searcher.workers.bounded_discovery import BoundedDiscoveryEngine

# The live campaign: 9 answerable sources, page_limit 40, first walk 64.
LIVE_PAGE_LIMIT = 40
LIVE_SOURCES = [
    "rebag",
    "wikimedia",
    "marginalia",
    "the_realreal",
    "komehyo",
    "kind",
    "byronesque",
    "heroine",
    "archive_org",
]
HUNGRY_CATALOG_PAGES = 64


def _engine_classes() -> list[type[Any]]:
    """Base and bounded. install_bounded_discovery() rebinds the module name."""
    base = BoundedDiscoveryEngine.__bases__[0]
    return [base, BoundedDiscoveryEngine]


def _page_budget(*, pages: int = LIVE_PAGE_LIMIT, sources: int = 9) -> Budget:
    return Budget(
        wall_seconds=300,
        source_limit=sources,
        page_limit=pages,
        browser_page_limit=0,
        image_limit=40,
        model_call_limit=0,
        byte_limit=50_000_000,
        monetary_limit=None,
        retry_limit=4,
        storage_limit=100_000_000,
    )


def _query() -> QueryVariant:
    return QueryVariant(
        query_id=new_id(),
        hypothesis_id="h",
        round=1,
        language="en",
        query_text="kind pumps",
        query_type=QueryType.EXACT_NAME,
    )


def test_share_formula_is_max_floor_and_even_split() -> None:
    assert CATALOG_PAGE_SHARE_FLOOR == 2
    # Live campaign: 40 pages, 9 sources → 40 // 9 = 4.
    assert catalog_page_share(40, 9) == 4
    assert catalog_page_share(40, 1) == 40
    # Many sources: floor keeps a useful walk.
    assert catalog_page_share(40, 24) == 2
    assert catalog_page_share(40, 40) == 2
    assert catalog_page_share(0, 9) == 0
    assert catalog_page_share(40, 0) == 0
    assert catalog_page_share(-1, 9) == 0


def test_catalog_caps_clip_to_the_share_and_the_remaining_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SEARCHER_CATALOG_PAGES_PER_SOURCE", raising=False)
    monkeypatch.delenv("SEARCHER_CATALOG_PAGES_PER_CAMPAIGN", raising=False)
    caps = catalog_caps_for_campaign(40, 9)
    assert caps.pages_per_source == 4
    assert caps.pages_per_campaign == 40
    # A solo source still cannot walk more pages than the campaign has.
    solo = catalog_caps_for_campaign(40, 1)
    assert solo.pages_per_source == 40
    assert solo.pages_per_campaign == 40


def test_both_run_methods_bind_the_catalog_share() -> None:
    """A fix only on DiscoveryEngine.run does not reach the API."""
    for cls in _engine_classes():
        source = inspect.getsource(cls.run)
        assert "_bind_catalog_walk_caps" in source, (
            f"{cls.__name__}.run() does not bind a catalogue page share; "
            "the first source will walk the env default and starve the rest"
        )


def test_page_catalog_is_called_with_bound_caps() -> None:
    base = BoundedDiscoveryEngine.__bases__[0]
    source = inspect.getsource(base._run_catalog_fallback)
    assert "caps=self._catalog_walk_caps" in source, (
        "page_catalog is still falling back to catalog_caps_from_env(); "
        "the campaign page budget never enters the walk"
    )


def _fake_plans(names: list[str], queries: list[QueryVariant]) -> list[SourcePlan]:
    return [
        SourcePlan(
            source_plan_id=new_id(),
            source_adapter=name,
            query_ids=[item.query_id for item in queries],
            admission=Admission(status=SourceAdmission.ADMITTED, basis="test"),
        )
        for name in names
    ]


def _run_hungry_campaign(
    engine_cls: type[Any],
    controller: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    pages: int = LIVE_PAGE_LIMIT,
    names: list[str] | None = None,
) -> tuple[Any, dict[str, int]]:
    """Each source tries to walk 64 catalogue pages unless the engine shared."""
    planned = list(names or LIVE_SOURCES)
    pages_taken: dict[str, int] = {}

    def fake_plan(
        self: Any,
        queries: list[QueryVariant],
        usage: Any = None,
        **kwargs: Any,
    ) -> list[SourcePlan]:
        del usage, kwargs
        self.names = tuple(planned)
        return _fake_plans(planned, queries)

    def fake_run_plan(
        self: Any, search_id: str, plan: Any, queries: Any, events: Any, cancel: Any
    ) -> tuple[str, list[Any]]:
        del queries, events, cancel
        usage = self.controller.usage(search_id)
        remaining = remaining_page_budget(usage)
        caps = getattr(self, "_catalog_walk_caps", None)
        want = caps.pages_per_source if caps is not None else HUNGRY_CATALOG_PAGES
        if remaining <= 0:
            raise BudgetExceeded("[BUDGET] pages", dimension="pages")
        take = min(int(want), remaining)
        if take:
            usage.consume(pages=take)
        pages_taken[plan.source_adapter] = take
        return SourceOutcome.SEARCHED_MATCHES_FOUND.value, []

    monkeypatch.setattr("searcher.sources.broker.SourceBroker.plan", fake_plan)
    # Patch the base _run_plan so Bounded's deadline wrapper still applies.
    base = BoundedDiscoveryEngine.__bases__[0]
    monkeypatch.setattr(base, "_run_plan", fake_run_plan)

    intent = make_intent()
    controller.create(intent, budget=_page_budget(pages=pages, sources=len(planned)))
    query = _query()
    controller.repos.upsert_query(intent.search_id, query)
    engine = engine_cls(controller, batch_size=2, max_work=4)
    try:
        summary = engine.run(intent.search_id, [query], source_names=planned)
    finally:
        engine.close()
    return summary, pages_taken


@pytest.mark.parametrize("engine_cls", _engine_classes(), ids=lambda cls: cls.__name__)
def test_hungry_catalog_does_not_starve_later_sources(
    engine_cls: type[Any],
    controller: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live shape: 40 pages, 9 sources, first walk wants 64.

    Before the share, one source completed and the rest were UNMEASURABLE.
    After, every planned source runs and no catalogue walk exceeds 1/N.
    """
    share = catalog_page_share(LIVE_PAGE_LIMIT, len(LIVE_SOURCES))
    assert share == 4

    summary, pages_taken = _run_hungry_campaign(engine_cls, controller, monkeypatch)
    completed = [
        name
        for name, outcome in summary.coverage.items()
        if outcome == SourceOutcome.SEARCHED_MATCHES_FOUND.value
    ]
    unmeasurable = [
        name
        for name, outcome in summary.coverage.items()
        if outcome == SourceOutcome.UNMEASURABLE.value
    ]

    assert len(completed) == len(LIVE_SOURCES), (
        f"{engine_cls.__name__}: expected all {len(LIVE_SOURCES)} sources to complete, "
        f"got {len(completed)} completed, UNMEASURABLE={unmeasurable}, "
        f"coverage={summary.coverage}, pages_taken={pages_taken}"
    )
    assert unmeasurable == [], (
        f"{engine_cls.__name__}: later sources were UNMEASURABLE because an "
        f"earlier source spent the page budget: {unmeasurable}; "
        f"pages_taken={pages_taken}"
    )
    assert "kind" in completed
    for name, taken in pages_taken.items():
        assert taken <= share, (
            f"{name} catalogue walk took {taken} pages; share is {share} "
            f"(max({CATALOG_PAGE_SHARE_FLOOR}, {LIVE_PAGE_LIMIT}//{len(LIVE_SOURCES)}))"
        )
    assert max(pages_taken.values(), default=0) <= share
    # More than one source must actually have run.
    assert len(pages_taken) > 1
    assert len(completed) > 1
