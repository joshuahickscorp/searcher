"""§32.2 schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from searcher.contracts.enums import (
    AdoptionDecision,
    Availability,
    CampaignState,
    DocumentClass,
    FactClass,
    FactOrigin,
    SourceOutcome,
    TerminalVerdict,
)
from searcher.contracts.primitives import (
    ClassifiedFact,
    DegradedLabel,
    ScoreInterval,
    fallback_outcome,
)
from searcher.core.errors import InvariantViolation
from searcher.core.time import parse_utc


def test_score_interval_requires_ordered_bounds() -> None:
    ScoreInterval(mean=0.5, lower_bound=0.4, upper_bound=0.7)
    with pytest.raises(ValidationError):
        ScoreInterval(mean=0.2, lower_bound=0.5, upper_bound=0.7)


def test_score_interval_unit_range() -> None:
    with pytest.raises(ValidationError):
        ScoreInterval(mean=1.2, lower_bound=0.0, upper_bound=1.0)


def test_seller_fact_cannot_be_observed() -> None:
    with pytest.raises(ValidationError):
        ClassifiedFact(value="Dior", fact_class=FactClass.OBSERVED, origin=FactOrigin.SELLER)


def test_seller_reported_fact_ok() -> None:
    fact = ClassifiedFact(
        value="Dior",
        fact_class=FactClass.REPORTED_BY_SELLER,
        origin=FactOrigin.SELLER,
    )
    assert fact.fact_class is FactClass.REPORTED_BY_SELLER


def test_fallback_cannot_emit_real() -> None:
    with pytest.raises(InvariantViolation):
        fallback_outcome("REAL", "degraded path")
    outcome = fallback_outcome("PARTIAL", "fixture")
    assert outcome.label is DegradedLabel.PARTIAL


def test_enums_cover_bible_values() -> None:
    assert FactClass.OBSERVED.value == "OBSERVED"
    assert SourceOutcome.SEARCHED_NO_MATCH.value == "SEARCHED_NO_MATCH"
    assert Availability.LIVE.value == "LIVE"
    assert CampaignState.CREATED.value == "CREATED"
    assert TerminalVerdict.COMPLETE.value == "COMPLETE"
    assert AdoptionDecision.REIMPLEMENT_FROM_CONTRACT.value == "REIMPLEMENT_FROM_CONTRACT"
    assert DocumentClass.PRODUCT.value == "product"
    assert DocumentClass.INDEX.value == "index"
    assert DocumentClass.OTHER.value == "other"
    assert len(CampaignState) == 25
    assert len(SourceOutcome) == 11
    assert len(DocumentClass) == 3


def test_utc_parse_rejects_naive() -> None:
    from searcher.core.errors import NaiveDatetimeError

    with pytest.raises(NaiveDatetimeError):
        parse_utc("2007-06-15T12:00:00")
