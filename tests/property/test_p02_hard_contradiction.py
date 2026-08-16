"""Property 2: adding a hard contradiction cannot raise bucket confidence."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import EvidencePolarity
from searcher.contracts.primitives import (
    EvidenceWeight,
    bucket_confidence,
    bucket_confidence_after_hard_contradiction,
)

_polarity = st.sampled_from(list(EvidencePolarity))


@st.composite
def weights(draw: st.DrawFn) -> list[EvidenceWeight]:
    n = draw(st.integers(min_value=1, max_value=8))
    out: list[EvidenceWeight] = []
    for i in range(n):
        out.append(
            EvidenceWeight(
                evidence_id=f"e{i}",
                family_id=f"f{i % 3}",
                polarity=draw(_polarity),
                weight=draw(st.floats(min_value=0.1, max_value=0.9)),
                hard=draw(st.booleans()),
            )
        )
    return out


@given(weights())
def test_adding_hard_contradiction_cannot_raise_bucket_confidence(
    existing: list[EvidenceWeight],
) -> None:
    previous = bucket_confidence(existing)
    contra = EvidenceWeight(
        evidence_id="hard-contra",
        family_id="contra",
        polarity=EvidencePolarity.CONTRADICTORY,
        weight=0.99,
        hard=True,
    )
    updated = bucket_confidence_after_hard_contradiction(previous, existing + [contra])
    assert updated <= previous + 1e-12
