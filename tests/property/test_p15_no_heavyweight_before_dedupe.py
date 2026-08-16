"""Property: no heavyweight call before deduplication (§28.2)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.core.errors import InvariantViolation
from searcher.retrieval.cost import HEAVYWEIGHT_STAGES, CostLedger, CostStage


@given(
    st.lists(
        st.sampled_from(list(CostStage)),
        min_size=1,
        max_size=12,
    )
)
def test_heavyweight_before_dedupe_is_rejected(stages: list[CostStage]) -> None:
    ledger = CostLedger(search_id="s")
    saw_dedupe = False
    for stage in stages:
        if stage is CostStage.DEDUPLICATION:
            ledger.mark_deduplicated()
            saw_dedupe = True
            continue
        if stage in HEAVYWEIGHT_STAGES and not saw_dedupe:
            try:
                ledger.record(stage)
            except InvariantViolation:
                continue
            raise AssertionError(f"{stage} ran before dedupe")
        else:
            ledger.record(stage)
    assert ledger.cheap_first_respected()
