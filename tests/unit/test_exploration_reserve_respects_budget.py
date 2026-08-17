"""The exploration reserve must never let total pages exceed the page budget.

Round 7 measured a live campaign reporting `pages_fetched=60` against
`page_limit=40`. The reserve was added so one source could not spend the whole
budget; if it instead hands each source a floor *on top of* the budget, it has
traded starvation for an overrun, and a page limit that can be exceeded is not
a limit.
"""

from __future__ import annotations

import pytest

from searcher.sources.engine import ExplorationReserve, exploration_page_allowance


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


@pytest.mark.xfail(
    reason=(
        "The reserve is per-round; page_limit is per-campaign. Each round rebinds it with "
        "a fresh page_budget, so N rounds can grant N x the limit. This reproduces round 7's "
        "live pages_fetched=60 against page_limit=40. The reserve itself is correct - every "
        "single-round invariant above holds - so the repair belongs where the per-round "
        "budget is derived, which must be the campaign remaining rather than the campaign "
        "total."
    ),
    strict=True,
)
def test_the_budget_is_a_campaign_limit_not_a_round_limit() -> None:
    budget, rounds = 40, 2
    names = tuple(f"s{i}" for i in range(9))
    total = 0
    for _ in range(rounds):
        reserve = ExplorationReserve(
            allowance=exploration_page_allowance(budget, len(names)),
            source_ids=names,
            page_budget=budget,
        )
        for _ in range(budget * 3):
            for name in names:
                if reserve.can_claim(name):
                    reserve.claim(name)
                    total += 1
    assert total <= budget, (
        f"{rounds} rounds granted {total} pages against a campaign limit of {budget}"
    )
