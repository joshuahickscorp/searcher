"""Sealed budget ceiling refusal."""

from __future__ import annotations

import pytest

from searcher.core.budgets import Budget, BudgetUsage
from searcher.core.errors import BudgetExceeded


def test_reserve_commit_tracks_usage() -> None:
    usage = BudgetUsage(Budget.fixture_default().seal())
    reservation = usage.reserve(pages=3)
    assert int(usage.used("pages")) == 3
    usage.commit(reservation)
    assert int(usage.committed("pages")) == 3
    assert int(usage.used("pages")) == 3


def test_ceiling_refusal() -> None:
    usage = BudgetUsage(Budget.fixture_default().seal())
    with pytest.raises(BudgetExceeded) as exc:
        usage.reserve(pages=51)
    assert exc.value.dimension == "pages"


def test_release_returns_capacity() -> None:
    usage = BudgetUsage(
        Budget(
            wall_seconds=10,
            source_limit=1,
            page_limit=2,
            browser_page_limit=0,
            image_limit=1,
            model_call_limit=0,
            byte_limit=10,
        ).seal()
    )
    held = usage.reserve(pages=2)
    with pytest.raises(BudgetExceeded):
        usage.reserve(pages=1)
    usage.release(held)
    usage.reserve(pages=1)


def test_sealed_digest_stable() -> None:
    budget = Budget.fixture_default()
    assert budget.seal().digest == budget.seal().digest
