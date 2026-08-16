"""Property 8: a dead listing cannot become Real."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import Availability, BucketPublic
from searcher.contracts.routing import require_live_for_real
from searcher.core.policy import GateView, route_public_bucket


@given(
    st.sampled_from(
        [Availability.SOLD, Availability.RESERVED, Availability.REMOVED, Availability.UNKNOWN]
    ),
    st.booleans(),
    st.floats(min_value=0.9, max_value=1.0),
    st.floats(min_value=0.8, max_value=1.0),
)
def test_dead_listing_cannot_become_real(
    availability: Availability,
    live_checked: bool,
    item_lb: float,
    auth_lb: float,
) -> None:
    view = GateView(
        item_match_lower_bound=item_lb,
        authenticity_lower_bound=auth_lb,
        evidence_completeness=0.9,
        availability=availability.value,
        live_checked=live_checked,
        destination_verified=True,
    )
    assert route_public_bucket(view) != "real"
    assert (
        require_live_for_real(
            availability=availability,
            live_checked=True,
            intended=BucketPublic.REAL,
        )
        is BucketPublic.HIDDEN
    )
