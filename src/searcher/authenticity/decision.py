"""Combine authenticity categories. Price cannot raise the interval."""

from __future__ import annotations

from searcher.authenticity.calibration import CalibrationTable, apply_calibration, public_label
from searcher.authenticity.contracts import CategorySignals
from searcher.authenticity.established import UNESTABLISHED_PREFIX
from searcher.contracts.enums import FactClass
from searcher.contracts.primitives import ScoreWithEvidence
from searcher.core.policy import apply_price_to_authenticity
from searcher.matching.scores import weighted_mean

AUTH_WEIGHTS = {
    "construction": 0.24,
    "label": 0.16,
    "logo": 0.12,
    "material": 0.12,
    "photo": 0.12,
    "originality": 0.08,
    "source": 0.08,
    "provenance": 0.08,
}


def combine_authenticity(
    *,
    construction: ScoreWithEvidence,
    labels: ScoreWithEvidence,
    logos: ScoreWithEvidence,
    materials: ScoreWithEvidence,
    photo_set: ScoreWithEvidence,
    originality: ScoreWithEvidence,
    source: ScoreWithEvidence,
    provenance: ScoreWithEvidence,
    price: ScoreWithEvidence,
    hard: list[str],
    soft: list[str],
    missing: list[str],
    completeness_value: float,
    table: CalibrationTable | None,
) -> CategorySignals:
    raw = _established_mean(
        [
            ("construction", construction),
            ("label", labels),
            ("logo", logos),
            ("material", materials),
            ("photo", photo_set),
            ("originality", originality),
            ("source", source),
            ("provenance", provenance),
        ]
    )
    # Completeness is a separate gate; when critical views are present and
    # nothing contradicts, do not let thin provenance drag the interval down.
    if not hard and completeness_value >= 0.65:
        raw = min(1.0, raw + 0.12)
    # Price may only pull down.
    raw = apply_price_to_authenticity(raw, price.interval.mean - 0.5)
    if hard:
        raw = min(raw, 0.22)
    interval, calibrated, ceiling = apply_calibration(raw, table)
    if hard:
        from searcher.matching.scores import apply_hard_penalty

        interval = apply_hard_penalty(interval, hard_count=len(hard))
    label = public_label(
        interval=interval,
        calibrated=calibrated,
        hard=hard,
        completeness_value=completeness_value,
    )
    return CategorySignals(
        construction=construction,
        labels=labels,
        logos=logos,
        materials=materials,
        photo_set=photo_set,
        originality=originality,
        source=source,
        provenance=provenance,
        price=price,
        hard=hard,
        soft=soft,
        missing=missing,
        completeness=completeness_value,
        calibrated=calibrated,
        interval=interval,
        public_label=label,
        authority_ceiling=ceiling if calibrated else "uncalibrated",
    )


def _score_is_established(score: ScoreWithEvidence) -> bool:
    if score.fact_class is FactClass.UNRESOLVED:
        return False
    return not any(item.startswith(UNESTABLISHED_PREFIX) for item in score.missing)


def _established_mean(parts: list[tuple[str, ScoreWithEvidence]]) -> float:
    pairs = [
        (AUTH_WEIGHTS[name], score.interval.mean)
        for name, score in parts
        if _score_is_established(score)
    ]
    if not pairs:
        return 0.5
    return weighted_mean(pairs)
