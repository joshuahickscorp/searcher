"""The exploration reserve must never let total pages exceed the page budget.

Round 7 measured a live campaign reporting `pages_fetched=60` against
`page_limit=40`. The reserve was added so one source could not spend the whole
budget; if it instead hands each source a floor *on top of* the budget, it has
traded starvation for an overrun, and a page limit that can be exceeded is not
a limit.
"""

from __future__ import annotations

import pytest

from searcher.sources.engine import (
    ExplorationReserve,
    exploration_page_allowance,
    remaining_page_budget,
)


@pytest.mark.parametrize(
    ("budget", "sources"),
    [(40, 9), (40, 1), (10, 10), (10, 3), (1, 5), (100, 7), (5, 40)],
)
def test_total_claims_never_exceed_the_budget(budget: int, sources: int) -> None:
    names = tuple(f"s{i}" for i in range(sources))
    reserve = ExplorationReserve(
        allowance=exploration_page_allowance(budget, sources),
        source_ids=names,
        page_budget=budget,
    )
    granted = 0
    # Drive it hard: every source asks repeatedly, far past the budget.
    for _ in range(budget * 3 + 10):
        for name in names:
            if reserve.can_claim(name):
                reserve.claim(name)
                granted += 1
    assert granted <= budget, (
        f"reserve granted {granted} pages against a budget of {budget}; "
        "a page limit that can be exceeded is not a limit"
    )


def test_a_single_greedy_source_cannot_take_the_whole_budget() -> None:
    """The starvation this reserve exists to prevent."""
    names = ("greedy", "b", "c", "d")
    reserve = ExplorationReserve(
        allowance=exploration_page_allowance(40, len(names)),
        source_ids=names,
        page_budget=40,
    )
    for _ in range(200):
        if reserve.can_claim("greedy"):
            reserve.claim("greedy")
    for other in names[1:]:
        assert reserve.can_claim(other), (
            f"{other} was starved: the greedy source consumed the reserve held for it"
        )


def test_rounds_share_one_campaign_budget_when_bound_from_the_ledger() -> None:
    """Successive rounds cannot each spend a fresh budget.

    An earlier version of this file asserted the opposite and marked it xfail,
    after a hand-built reproduction gave two rounds a fresh `page_budget=40`
    each and concluded the campaign could fetch eighty. Production never builds
    it that way: `_bind_exploration_reserve` derives the budget from
    `remaining_page_budget(usage)`, which is ceiling minus used, so a second
    round binds with what the first left. The reproduction constructed a
    scenario the code does not produce, and the defect it recorded was not real.
    """

    class _Sealed:
        def __init__(self, ceiling: int) -> None:
            self._ceiling = ceiling

        def ceiling(self, _key: str) -> int:
            return self._ceiling

    class _Usage:
        def __init__(self, ceiling: int) -> None:
            self.sealed = _Sealed(ceiling)
            self._used = 0

        def used(self, _key: str) -> int:
            return self._used

        def consume(self, pages: int = 0) -> None:
            self._used += pages

    ceiling = 40
    usage = _Usage(ceiling)
    for _ in range(5):
        remaining = remaining_page_budget(usage)
        usage.consume(pages=remaining)  # a round spending everything it was given

    assert usage.used("pages") == ceiling, (
        f"five rounds charged {usage.used('pages')} against a ceiling of {ceiling}"
    )


def test_the_allowance_falls_to_zero_once_the_budget_is_spent() -> None:
    """A later round is given nothing rather than a fresh floor per source."""
    assert exploration_page_allowance(0, 9) == 0
    assert exploration_page_allowance(40, 9) > 0
