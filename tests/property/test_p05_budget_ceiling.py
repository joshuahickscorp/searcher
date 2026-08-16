"""Property 5: budget usage never exceeds the sealed ceiling."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.core.budgets import Budget, BudgetUsage
from searcher.core.errors import BudgetExceeded


@given(
    st.integers(min_value=0, max_value=30),
    st.integers(min_value=0, max_value=30),
    st.integers(min_value=1, max_value=15),
)
def test_budget_usage_never_exceeds_sealed_ceiling(a: int, b: int, ceiling: int) -> None:
    budget = Budget(
        wall_seconds=ceiling,
        source_limit=ceiling,
        page_limit=ceiling,
        browser_page_limit=ceiling,
        image_limit=ceiling,
        model_call_limit=ceiling,
        byte_limit=ceiling,
        retry_limit=ceiling,
        storage_limit=ceiling,
    )
    usage = BudgetUsage(budget.seal())
    try:
        usage.consume(pages=a)
        usage.consume(pages=b)
    except BudgetExceeded:
        pass
    assert usage.never_exceeds_ceiling()
    assert int(usage.used("pages")) <= ceiling
