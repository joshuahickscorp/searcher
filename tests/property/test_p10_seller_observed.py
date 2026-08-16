"""Property 10: seller text cannot create an OBSERVED fact."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from pytest import raises

from searcher.contracts.enums import FactClass, FactOrigin
from searcher.contracts.primitives import ClassifiedFact


@given(st.text(max_size=40), st.sampled_from([None, "Dior", "GAT", "42"]))
def test_seller_text_cannot_create_observed_fact(note: str, value: str | None) -> None:
    del note
    with raises(ValidationError):
        ClassifiedFact(value=value, fact_class=FactClass.OBSERVED, origin=FactOrigin.SELLER)
