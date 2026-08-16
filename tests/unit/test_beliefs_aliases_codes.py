"""Belief updates, alias promotion, product-code rules."""

from __future__ import annotations

from searcher.contracts.enums import FactClass, FactOrigin
from searcher.hypotheses.aliases import (
    AliasEvidence,
    can_promote_alias,
    promote_or_hold,
    seller_title_alone_cannot_promote,
)
from searcher.hypotheses.beliefs import make_belief, update_belief
from searcher.hypotheses.product_codes import assess_code, is_size_code, normalize_product_code


def test_belief_update_keeps_history() -> None:
    belief = make_belief(
        "2007", confidence=0.6, fact_class=FactClass.USER_SUPPLIED, origin=FactOrigin.USER
    )
    later = update_belief(
        belief,
        value="2007",
        confidence=0.2,
        fact_class=FactClass.CONTRADICTED,
        origin=FactOrigin.USER,
        reason="label says 2008",
        evidence_ref="ocr:2008",
    )
    assert later.fact_class is FactClass.CONTRADICTED
    assert later.update_history[-1].previous_value == "2007"
    assert "ocr:2008" in later.evidence


def test_single_low_confidence_seller_cannot_promote() -> None:
    evidence = [
        AliasEvidence(
            alias="street nickname",
            source_family="seller",
            authority="listing",
            confidence=0.3,
        )
    ]
    assert seller_title_alone_cannot_promote(evidence)
    assert not can_promote_alias(evidence)
    held = promote_or_hold(evidence)
    assert held is not None
    assert held.belief.confidence < 0.2
    assert held.belief.fact_class is not FactClass.OBSERVED


def test_two_families_promote() -> None:
    evidence = [
        AliasEvidence("archive name", "forum", "community", 0.5),
        AliasEvidence("archive name", "catalog", "catalog", 0.55),
    ]
    assert can_promote_alias(evidence)


def test_high_authority_promotes() -> None:
    evidence = [AliasEvidence("official", "lookbook", "lookbook", 0.8)]
    assert can_promote_alias(evidence)


def test_product_code_normalization_and_size() -> None:
    assert normalize_product_code("ab-12 34") == "AB1234"
    assert is_size_code("42")
    assert is_size_code("EU 41")
    assert is_size_code("26.5cm")
    size = assess_code(
        "42", region_level_ocr=True, structured_source=False, consistent_across_candidates=True
    )
    assert size.is_size
    assert not size.promotable
    weak = assess_code(
        "XYZ99A",
        region_level_ocr=False,
        structured_source=False,
        consistent_across_candidates=False,
    )
    assert not weak.promotable
    ok = assess_code(
        "XYZ99A",
        region_level_ocr=True,
        structured_source=False,
        consistent_across_candidates=True,
    )
    assert ok.promotable
