"""Property 12: price alone cannot raise authenticity."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.core.policy import apply_price_to_authenticity


@given(
    st.floats(min_value=0.0, max_value=1.0),
    st.floats(min_value=0.0, max_value=1.0),
)
def test_price_alone_cannot_raise_authenticity(base: float, positive_price: float) -> None:
    updated = apply_price_to_authenticity(base, positive_price)
    assert updated <= base + 1e-12
