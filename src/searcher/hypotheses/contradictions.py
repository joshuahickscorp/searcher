"""§12.5 contradiction reweights the portfolio; it does not force a conclusion."""

from __future__ import annotations

from searcher.contracts.enums import FactClass, FactOrigin, HypothesisStatus
from searcher.contracts.models import ItemHypothesis, ReferenceAnalysis, TextObservation
from searcher.hypotheses.beliefs import lower_confidence, update_belief


def _ocr_of(analysis: ReferenceAnalysis, kind: str) -> list[TextObservation]:
    return [
        item
        for item in analysis.text_and_marks
        if item.kind == kind and not item.injection_candidate
    ]


def apply_contradictions(
    hypotheses: list[ItemHypothesis], analysis: ReferenceAnalysis
) -> list[ItemHypothesis]:
    ocr_brands = [item.text for item in _ocr_of(analysis, "brand")]
    ocr_years = [
        item.text
        for item in analysis.text_and_marks
        if item.kind == "season" and item.text.isdigit() and len(item.text) == 4
    ]
    updated: list[ItemHypothesis] = []
    for hyp in hypotheses:
        contradictions = list(hyp.contradictions)
        posterior = hyp.posterior
        brand = hyp.brand
        year = hyp.year
        if (
            brand.value
            and ocr_brands
            and all(
                brand.value.lower() not in ob.lower() and ob.lower() not in brand.value.lower()
                for ob in ocr_brands
            )
            and brand.fact_class is FactClass.USER_SUPPLIED
        ):
            brand = lower_confidence(brand, reason="ocr_brand_conflicts_user_brand")
            contradictions.append("ocr_brand_conflicts_user_brand")
            posterior *= 0.7
        if (
            year.value
            and year.value.isdigit()
            and ocr_years
            and year.value not in ocr_years
            and year.origin is FactOrigin.USER
        ):
            year = update_belief(
                year,
                value=year.value,
                confidence=max(0.1, year.confidence * 0.5),
                fact_class=FactClass.CONTRADICTED,
                origin=year.origin,
                reason="ocr_or_visual_year_conflicts_user_year",
            )
            contradictions.append("year_conflicts_extracted_year")
            posterior *= 0.65
        status = hyp.status
        if posterior < 0.04 and status is HypothesisStatus.ACTIVE:
            status = HypothesisStatus.ARCHIVED
        updated.append(
            hyp.model_copy(
                update={
                    "brand": brand,
                    "year": year,
                    "contradictions": contradictions,
                    "posterior": round(max(0.01, posterior), 4),
                    "status": status,
                }
            )
        )
    active = [h for h in updated if h.status is HypothesisStatus.ACTIVE]
    archived = [h for h in updated if h.status is not HypothesisStatus.ACTIVE]
    total = sum(h.posterior for h in active) or 1.0
    renormalized = [
        h.model_copy(update={"posterior": round(h.posterior / total, 4)}) for h in active
    ]
    return renormalized + archived


def contradict_user_field(
    hypothesis: ItemHypothesis,
    *,
    field: str,
    observed_value: str,
    evidence_ref: str,
) -> ItemHypothesis:
    """Apply visual/extracted evidence against a user-supplied field.

    Used by tests and by later waves when structured evidence arrives.
    """
    current = getattr(hypothesis, field)
    updated = update_belief(
        current,
        value=current.value,
        confidence=max(0.05, current.confidence * 0.4),
        fact_class=FactClass.CONTRADICTED,
        origin=current.origin,
        reason=f"evidence {observed_value} contradicts user {field}",
        evidence_ref=evidence_ref,
    )
    posterior = max(0.02, hypothesis.posterior * 0.55)
    contradictions = list(hypothesis.contradictions) + [f"{field}_contradicted_by_{evidence_ref}"]
    return hypothesis.model_copy(
        update={
            field: updated,
            "posterior": round(posterior, 4),
            "contradictions": contradictions,
        }
    )
