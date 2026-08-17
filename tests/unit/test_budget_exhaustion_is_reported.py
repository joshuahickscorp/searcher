"""A budget that runs out is a fact to report, not a reason to stop reporting.

A live footwear campaign planned nine sources and completed one. Coverage
recorded rebag and nothing else - zero blocked, zero in progress - and the
reader was told "Hidden: 8 because it is a different product" while the source
holding their item had never been opened.

The cause: `usage.consume(sources=1)` was guarded in the per-plan loop, but the
`_run_plan` call on the next line was not. A page-budget exhaustion inside one
source raised `BudgetExceeded` straight out of `run()`, and every source after
it disappeared without a trace.
"""

from __future__ import annotations

from typing import Any

import pytest
from tests.conftest import make_budget, make_intent

from searcher.contracts.enums import QueryType, SourceOutcome
from searcher.contracts.models import QueryVariant
from searcher.core.errors import BudgetExceeded
from searcher.core.ids import new_id


def test_budget_exhaustion_mid_source_still_reports_every_planned_source(
    controller: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drive the real loop, not a copy of it.

    `_run_plan` is replaced so the second source raises the same
    `BudgetExceeded` a page fetch raises. Every planned source must still
    appear in coverage.
    """
    # install_bounded_discovery() permanently rebinds
    # searcher.sources.engine.DiscoveryEngine to BoundedDiscoveryEngine with no
    # undo, so importing the name gets whichever class ran last in the suite.
    # Both need the guard, so both are exercised by name rather than by import.
    from searcher.sources.engine import DiscoveryEngine as EngineName
    from searcher.workers.bounded_discovery import BoundedDiscoveryEngine

    DiscoveryEngine = EngineName if EngineName is not BoundedDiscoveryEngine else EngineName
    planned = ["wikimedia", "kind", "archive_org"]
    seen: list[str] = []

    def fake_run_plan(
        self: Any, search_id: str, plan: Any, queries: Any, events: Any, cancel: Any
    ) -> tuple[str, list[Any]]:
        seen.append(plan.source_adapter)
        if len(seen) == 2:
            raise BudgetExceeded("[BUDGET] pages", dimension="pages")
        return (SourceOutcome.SEARCHED_NO_MATCH.value, [])

    monkeypatch.setattr(DiscoveryEngine, "_run_plan", fake_run_plan)

    intent = make_intent()
    controller.create(intent, budget=make_budget())
    query = QueryVariant(
        query_id=new_id(),
        hypothesis_id="h",
        round=1,
        language="en",
        query_text="probe",
        query_type=QueryType.EXACT_NAME,
    )
    controller.repos.upsert_query(intent.search_id, query)

    engine = DiscoveryEngine(controller, batch_size=2, max_work=4)
    try:
        summary = engine.run(intent.search_id, [query], source_names=planned)
    finally:
        engine.close()

    missing = [name for name in planned if name not in summary.coverage]
    assert missing == [], (
        f"sources vanished from coverage when the budget ran out: {missing}; "
        f"coverage was {summary.coverage}"
    )
    assert summary.coverage["archive_org"] == SourceOutcome.NOT_ATTEMPTED.value


def test_engine_loop_guards_the_run_plan_call() -> None:
    """The guard must be around `_run_plan`, not only around `consume`."""
    import inspect

    from searcher.sources.engine import DiscoveryEngine

    # Both the base engine and the bounded subclass define run(), and the
    # module attribute may be either after install_bounded_discovery(). Check
    # every run() that a campaign can actually execute.
    from searcher.workers.bounded_discovery import BoundedDiscoveryEngine

    for cls in (DiscoveryEngine, BoundedDiscoveryEngine):
        _assert_guarded(inspect.getsource(cls.run), cls.__name__)


def _assert_guarded(source: str, name: str) -> None:
    if "self._run_plan(" not in source:
        return
    call = source.index("self._run_plan(")
    before = source[:call]
    guard = before.rindex("try:")
    assert "except" not in before[guard:], (
        f"{name}._run_plan is not inside a try block; a BudgetExceeded raised by "
        "a page fetch will unwind past every remaining source"
    )
    assert "NOT_ATTEMPTED" in source, (
        f"{name} must record sources abandoned for budget as NOT_ATTEMPTED"
    )
