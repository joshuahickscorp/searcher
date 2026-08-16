"""Property 11: source reputation cannot erase a hard visual veto."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.core.policy import apply_reputation_to_vetoes


@given(
    st.lists(st.text(min_size=1, max_size=12), min_size=1, max_size=4),
    st.floats(min_value=0.0, max_value=1.0),
    st.sampled_from(["real", "possibly_real", "hidden"]),
)
def test_source_reputation_cannot_erase_hard_visual_veto(
    vetoes: list[str], reputation: float, bucket: str
) -> None:
    result = apply_reputation_to_vetoes(
        hard_visual_vetoes=vetoes,
        source_reputation=reputation,
        public_bucket=bucket,
    )
    assert result == "hidden"
