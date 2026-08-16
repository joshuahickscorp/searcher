"""Property 3: deleting evidence cannot raise a lower confidence bound."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import EvidencePolarity
from searcher.contracts.primitives import (
    EvidenceWeight,
    compute_interval,
    lower_bound_after_removal,
)

_polarity = st.sampled_from(list(EvidencePolarity))


@st.composite
def weights(draw: st.DrawFn) -> list[EvidenceWeight]:
    n = draw(st.integers(min_value=2, max_value=8))
    out: list[EvidenceWeight] = []
    for i in range(n):
        out.append(
            EvidenceWeight(
                evidence_id=f"e{i}",
                family_id=f"f{i}",
                polarity=draw(_polarity),
                weight=draw(st.floats(min_value=0.05, max_value=0.95)),
                hard=draw(st.booleans()),
            )
        )
    return out


@given(weights())
def test_deleting_evidence_cannot_raise_lower_bound(existing: list[EvidenceWeight]) -> None:
    previous = compute_interval(existing)
    index = len(existing) // 2
    remaining = existing[:index] + existing[index + 1 :]
    updated = lower_bound_after_removal(previous, remaining)
    assert updated.lower_bound <= previous.lower_bound + 1e-12
