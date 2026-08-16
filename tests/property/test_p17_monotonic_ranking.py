"""§21.4 monotonic constraints at the ranking helpers."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import EvidencePolarity
from searcher.contracts.primitives import EvidenceWeight, compute_interval
from searcher.ranking.monotonic import (
    after_hard_contradiction,
    after_removal,
    authenticity_after_price,
    badge_cannot_override,
    bucket_after_reputation,
    user_text_cannot_override,
)

_polarity = st.sampled_from(list(EvidencePolarity))


@st.composite
def weights(draw: st.DrawFn) -> list[EvidenceWeight]:
    n = draw(st.integers(min_value=1, max_value=6))
    return [
        EvidenceWeight(
            evidence_id=f"e{i}",
            family_id=f"f{i % 3}",
            polarity=draw(_polarity),
            weight=draw(st.floats(min_value=0.1, max_value=0.9)),
            hard=draw(st.booleans()),
        )
        for i in range(n)
    ]


@given(weights())
def test_hard_contradiction_cannot_raise(existing: list[EvidenceWeight]) -> None:
    previous = compute_interval(existing).lower_bound
    extra = EvidenceWeight(
        evidence_id="h",
        family_id="hx",
        polarity=EvidencePolarity.CONTRADICTORY,
        weight=0.9,
        hard=True,
    )
    assert after_hard_contradiction(previous, existing + [extra]) <= previous + 1e-12


@given(weights())
def test_removal_cannot_raise_lower(existing: list[EvidenceWeight]) -> None:
    previous = compute_interval(existing)
    remaining = existing[:-1]
    updated = after_removal(previous, remaining)
    assert updated.lower_bound <= previous.lower_bound + 1e-12


@given(st.floats(min_value=0.0, max_value=1.0), st.floats(min_value=0.0, max_value=1.0))
def test_price_cannot_raise_authenticity(base: float, price: float) -> None:
    assert authenticity_after_price(base, price) <= base + 1e-12


@given(st.floats(min_value=0.0, max_value=1.0))
def test_reputation_cannot_override_mismatch(rep: float) -> None:
    assert bucket_after_reputation(["wrong-model"], rep, "real") == "hidden"


@given(st.booleans())
def test_user_text_cannot_override_visual(agree: bool) -> None:
    assert user_text_cannot_override(["eyelet-count-mismatch"], agree, "real") == "hidden"


@given(st.booleans())
def test_badge_cannot_override_physical(badge: bool) -> None:
    assert badge_cannot_override(["construction-heel"], badge, "real") == "hidden"
