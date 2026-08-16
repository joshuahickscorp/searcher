"""User text is a hypothesis. Visual/extracted evidence can contradict it."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import FactClass, FactOrigin
from searcher.contracts.models import ItemHypothesis, VisualSignature
from searcher.core.ids import new_id
from searcher.hypotheses.beliefs import make_belief
from searcher.hypotheses.contradictions import contradict_user_field


def _b(value: str | None, cls: FactClass, origin: FactOrigin, conf: float) -> object:
    return make_belief(value, confidence=conf, fact_class=cls, origin=origin)


def _hyp(year: str) -> ItemHypothesis:
    empty = _b(None, FactClass.UNRESOLVED, FactOrigin.SYSTEM, 0.0)
    return ItemHypothesis(
        hypothesis_id=new_id(),
        search_id="s",
        category="footwear",
        brand=_b("Brand", FactClass.USER_SUPPLIED, FactOrigin.USER, 0.6),
        model_name=_b("Model", FactClass.USER_SUPPLIED, FactOrigin.USER, 0.5),
        line=empty,
        designer=empty,
        season=empty,
        year=_b(year, FactClass.USER_SUPPLIED, FactOrigin.USER, 0.7),
        colourway=empty,
        visual_signature=VisualSignature(),
        posterior=0.6,
    )


@given(st.integers(min_value=1990, max_value=2024))
def test_user_year_can_be_contradicted(year: int) -> None:
    hyp = _hyp(str(year))
    other = str(year + 1)
    updated = contradict_user_field(
        hyp, field="year", observed_value=other, evidence_ref="ocr-year"
    )
    assert updated.year.fact_class is FactClass.CONTRADICTED
    assert updated.posterior < hyp.posterior
    assert updated.year.value == str(year)
    assert any("year" in item for item in updated.contradictions)
