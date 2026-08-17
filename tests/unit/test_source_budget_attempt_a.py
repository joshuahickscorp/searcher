"""Reserve a per-source exploration floor before any source may exploit.

The live footwear campaign: page_limit 40, pages_fetched 41, sources_completed
1 of 9. Catalogue sharing cut the feed walk from 64 pages to a 1/N share, but
non-catalogue frontier fetches still drew on the same page budget. The first
source spent it; the other eight were UNMEASURABLE.

Attempt A holds a minimum per-source exploration allowance. A source may spend
more only from the unreserved remainder. The floor is the existing catalogue
share floor, not a raised budget, threshold, or Bible default.
"""

from __future__ import annotations

import inspect
import threading
from typing import Any

import pytest
from tests.conftest import make_intent

from searcher.contracts.enums import FetchMode, QueryType, SourceAdmission, SourceOutcome
from searcher.contracts.models import Admission, FetchResult, QueryVariant, SourcePlan
from searcher.core.budgets import Budget
from searcher.core.errors import BudgetExceeded
from searcher.core.ids import new_id
from searcher.sources.engine import (
    CATALOG_PAGE_SHARE_FLOOR,
    ExplorationReserve,
    catalog_page_share,
    exploration_page_allowance,
    remaining_page_budget,
)
from searcher.sources.fetch_modes import FetchedDocument
from searcher.sources.manifest import build_manifest
from searcher.workers.bounded_discovery import BoundedDiscoveryEngine

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
# The hole catalogue sharing left open: one source's frontier walk.
HUNGRY_FRONTIER_PAGES = 40


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


def test_exploration_allowance_is_the_existing_floor_when_it_fits() -> None:
    assert CATALOG_PAGE_SHARE_FLOOR == 2
    # Live campaign: 2 * 9 = 18 <= 40, so each source is guaranteed 2.
    assert exploration_page_allowance(40, 9) == 2
    # When the floor would over-reserve, fall back to remaining // N.
    assert exploration_page_allowance(10, 9) == 1
    assert exploration_page_allowance(5, 9) == 0
    assert exploration_page_allowance(40, 1) == 2
    assert exploration_page_allowance(0, 9) == 0
    assert exploration_page_allowance(40, 0) == 0


def test_first_source_may_exploit_only_the_unreserved_remainder() -> None:
    """Attempt A is not a 1/N cap. Leftover pages are exploit, after the floor."""
    names = tuple(LIVE_SOURCES)
    allowance = exploration_page_allowance(LIVE_PAGE_LIMIT, len(names))
    assert allowance == 2
    reserve = ExplorationReserve(allowance, names, LIVE_PAGE_LIMIT)
    taken = 0
    for _ in range(LIVE_PAGE_LIMIT):
        if not reserve.claim("rebag"):
            break
        taken += 1
    # 2 exploration + (40 - 9*2) exploit = 24. More than the catalogue 1/N share.
    assert taken == 24
    assert taken > catalog_page_share(LIVE_PAGE_LIMIT, len(names))
    # The other eight still have their floor.
    for name in names[1:]:
        assert reserve.claim(name)
        assert reserve.claim(name)
        assert not reserve.claim(name)
    assert reserve.claimed_total == LIVE_PAGE_LIMIT


def test_finishing_a_source_releases_unused_allowance_into_the_exploit_pool() -> None:
    reserve = ExplorationReserve(2, ("rebag", "kind", "wikimedia"), 10)
    assert reserve.claim("rebag")
    reserve.release_unused("kind")
    reserve.release_unused("wikimedia")
    # 1 used, 9 left, no one else still holds a floor.
    extra = 0
    while reserve.claim("rebag"):
        extra += 1
    assert extra == 9
    assert reserve.pages_taken()["rebag"] == 10


def test_concurrent_claims_cannot_eat_the_held_floor() -> None:
    reserve = ExplorationReserve(2, tuple(LIVE_SOURCES), LIVE_PAGE_LIMIT)
    taken = {name: 0 for name in LIVE_SOURCES}

    def eat(name: str) -> None:
        while reserve.claim(name):
            taken[name] += 1

    workers = [threading.Thread(target=eat, args=(name,)) for name in LIVE_SOURCES]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert sum(taken.values()) == LIVE_PAGE_LIMIT
    assert min(taken.values()) >= 2


def test_both_run_methods_bind_the_exploration_reserve() -> None:
    """A fix only on DiscoveryEngine.run does not reach the API."""
    for cls in _engine_classes():
        source = inspect.getsource(cls.run)
        assert "_bind_exploration_reserve" in source, (
            f"{cls.__name__}.run() does not bind an exploration reserve; "
            "the first source will spend the frontier on the whole page budget"
        )


def test_fetch_and_frontier_and_catalog_consult_the_reserve() -> None:
    base = BoundedDiscoveryEngine.__bases__[0]
    fetch_src = inspect.getsource(base._fetch_item)
    assert "reserve.claim" in fetch_src, (
        "_fetch_item does not claim the exploration reserve; "
        "frontier and catalogue fetches can still starve later sources"
    )
    plan_src = inspect.getsource(base._run_source_plan)
    assert "_source_may_fetch_more" in plan_src, (
        "the frontier loop does not stop when this source would spend "
        "another source's exploration floor"
    )
    catalog_src = inspect.getsource(base._run_catalog_fallback)
    assert "_source_may_fetch_more" in catalog_src


def test_no_budget_or_floor_default_was_raised() -> None:
    from searcher.workers import api_campaign

    source = inspect.getsource(api_campaign.create_api_campaign)
    assert "page_limit=40 if cfg.live_discovery else 0" in source
    assert "source_limit=len(uncredentialed_source_names())" in source
    assert CATALOG_PAGE_SHARE_FLOOR == 2
    assert exploration_page_allowance(40, 9) == 2


def _run_hungry_frontier(
    engine_cls: type[Any],
    controller: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    pages: int = LIVE_PAGE_LIMIT,
    names: list[str] | None = None,
    respect_reserve: bool = True,
) -> tuple[Any, dict[str, int]]:
    """Each source tries to fetch 40 frontier pages unless the reserve holds."""
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
        reserve = getattr(self, "_exploration_reserve", None) if respect_reserve else None
        taken = 0
        for _ in range(HUNGRY_FRONTIER_PAGES):
            remaining = remaining_page_budget(usage)
            if remaining <= 0:
                if taken == 0:
                    raise BudgetExceeded("[BUDGET] pages", dimension="pages")
                break
            if reserve is not None and not reserve.claim(plan.source_adapter):
                break
            usage.consume(pages=1)
            taken += 1
        pages_taken[plan.source_adapter] = taken
        if taken == 0:
            return SourceOutcome.UNMEASURABLE.value, []
        return SourceOutcome.SEARCHED_MATCHES_FOUND.value, []

    monkeypatch.setattr("searcher.sources.broker.SourceBroker.plan", fake_plan)
    # Patch the body, not the wrapper, so unused allowance is still released.
    base = BoundedDiscoveryEngine.__bases__[0]
    monkeypatch.setattr(base, "_run_source_plan", fake_run_plan)

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


def _measurement(
    planned: list[str],
    summary: Any,
    pages_taken: dict[str, int],
) -> dict[str, Any]:
    searched = {
        SourceOutcome.SEARCHED_MATCHES_FOUND.value,
        SourceOutcome.SEARCHED_NO_MATCH.value,
    }
    attempted = [name for name in planned if name in summary.coverage]
    reached = [name for name, taken in pages_taken.items() if taken > 0]
    completed = [
        name
        for name, outcome in summary.coverage.items()
        if outcome in searched
    ]
    unmeasurable = [
        name
        for name, outcome in summary.coverage.items()
        if outcome == SourceOutcome.UNMEASURABLE.value
    ]
    if unmeasurable and len(completed) < len(planned):
        reason = "page budget exhausted before later sources could explore"
    elif len(completed) == len(planned):
        reason = "all planned sources completed; exploration floor held"
    else:
        reason = "mixed coverage; see per-source pages"
    return {
        "planned": list(planned),
        "attempted": attempted,
        "reached": reached,
        "completed": completed,
        "unmeasurable": unmeasurable,
        "pages_per_source": dict(pages_taken),
        "termination_reason": reason,
    }


@pytest.mark.parametrize("engine_cls", _engine_classes(), ids=lambda cls: cls.__name__)
def test_hungry_frontier_reaches_several_sources(
    engine_cls: type[Any],
    controller: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live shape: 40 pages, 9 sources, first frontier wants 40.

    Before the reserve, one source completed and the rest were UNMEASURABLE.
    After, at least three sources run and each unstarted source keeps its floor.
    """
    allowance = exploration_page_allowance(LIVE_PAGE_LIMIT, len(LIVE_SOURCES))
    assert allowance == 2

    summary, pages_taken = _run_hungry_frontier(engine_cls, controller, monkeypatch)
    report = _measurement(LIVE_SOURCES, summary, pages_taken)
    print(f"\nATTEMPT_A {engine_cls.__name__} {report}")

    assert len(report["planned"]) == 9
    assert len(report["reached"]) >= 3, (
        f"{engine_cls.__name__}: expected at least 3 sources reached, "
        f"got {report}"
    )
    assert len(report["completed"]) >= 3, (
        f"{engine_cls.__name__}: expected at least 3 sources completed, "
        f"got {report}"
    )
    assert "kind" in report["reached"]
    assert report["unmeasurable"] == [], (
        f"{engine_cls.__name__}: later sources were UNMEASURABLE because an "
        f"earlier source spent the page budget: {report}"
    )
    # Every source that ran got at least the exploration floor.
    for name, taken in pages_taken.items():
        assert taken >= allowance, f"{name} took {taken}, floor is {allowance}"
    # The first source may exploit, but not into the others' floor.
    assert max(pages_taken.values(), default=0) <= (
        LIVE_PAGE_LIMIT - allowance * (len(LIVE_SOURCES) - 1)
    )
    assert sum(pages_taken.values()) <= LIVE_PAGE_LIMIT


def test_without_the_reserve_one_source_still_starves_the_rest(
    controller: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Document the before-measurement: the hole this attempt closes."""
    engine_cls = BoundedDiscoveryEngine.__bases__[0]
    summary, pages_taken = _run_hungry_frontier(
        engine_cls, controller, monkeypatch, respect_reserve=False
    )
    report = _measurement(LIVE_SOURCES, summary, pages_taken)
    print(f"\nATTEMPT_A BEFORE {engine_cls.__name__} {report}")
    starved = [
        name
        for name, outcome in summary.coverage.items()
        if outcome
        in {
            SourceOutcome.UNMEASURABLE.value,
            SourceOutcome.NOT_ATTEMPTED.value,
        }
    ]
    assert len(report["completed"]) == 1
    assert report["pages_per_source"].get("rebag") == HUNGRY_FRONTIER_PAGES
    assert len(starved) == 8


def test_fetch_item_will_not_spend_another_sources_exploration(
    controller: Any,
) -> None:
    intent = make_intent()
    controller.create(intent, budget=_page_budget(pages=10, sources=3))
    engine_cls = BoundedDiscoveryEngine.__bases__[0]
    engine = engine_cls(controller, batch_size=2, max_work=4)
    try:
        usage = controller.usage(intent.search_id)
        engine._exploration_reserve = ExplorationReserve(
            allowance=2,
            source_ids=("rebag", "kind", "wikimedia"),
            page_budget=10,
        )

        class _Adapter:
            pass

        class _Escalator:
            def __init__(self, inner_usage: Any) -> None:
                self.usage = inner_usage

            def fetch(self, url: str, manifest: Any, **kwargs: Any) -> FetchedDocument:
                del manifest, kwargs
                self.usage.consume(pages=1, bytes=0)
                return FetchedDocument(
                    result=FetchResult(
                        attempt_id=new_id(),
                        url=url,
                        outcome=SourceOutcome.SEARCHED_NO_MATCH,
                        mode=FetchMode.HTTP,
                    ),
                    body=b"",
                    headers={},
                    final_url=url,
                )

        escalator = _Escalator(usage)
        manifest = build_manifest(
            source_id="rebag",
            adapter="rebag",
            domain="www.rebag.com",
            access_method="http_get",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="public product pages",
        )
        fetched = 0
        held = 0
        for _ in range(10):
            doc = engine._fetch_item(
                _Adapter(),
                escalator,  # type: ignore[arg-type]
                "https://www.rebag.com/products/x",
                manifest,
            )
            note = doc.result.classification_note or ""
            if "reserved" in note:
                held += 1
            else:
                fetched += 1
        # 10 pages, 3 sources, floor 2: rebag can take 10 - 4 = 6.
        assert fetched == 6
        assert held >= 1
        assert remaining_page_budget(usage) == 4
        assert engine._exploration_reserve.pages_taken()["rebag"] == 6
    finally:
        engine.close()
