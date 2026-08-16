"""Property 9: a blocked source cannot be recorded as SEARCHED_NO_MATCH."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from pytest import raises

from searcher.contracts.enums import BLOCKED_SOURCE_OUTCOMES, FAILED_SOURCE_OUTCOMES, SourceOutcome
from searcher.contracts.routing import as_searched_no_match
from searcher.core.errors import InvariantViolation


@given(
    st.sampled_from(sorted(BLOCKED_SOURCE_OUTCOMES | FAILED_SOURCE_OUTCOMES, key=lambda o: o.value))
)
def test_blocked_source_cannot_be_searched_no_match(outcome: SourceOutcome) -> None:
    with raises(InvariantViolation):
        as_searched_no_match(outcome)
