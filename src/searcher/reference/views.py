"""§11.6 view classification. Labels are probabilistic, never asserted."""

from __future__ import annotations

from searcher.contracts.enums import FactClass, ViewHypothesis
from searcher.contracts.models import TextObservation, ViewInventoryEntry


def classify_view(
    *,
    crop_id: str,
    width: int,
    height: int,
    region: tuple[float, float, float, float],
    parent_width: int,
    parent_height: int,
    ocr: list[TextObservation],
    subject_area: float,
) -> ViewInventoryEntry:
    aspect = width / max(1, height)
    kinds = {item.kind for item in ocr}
    texts = " ".join(item.text.lower() for item in ocr)
    if "label" in kinds or "size" in kinds or "made in" in texts or "size" in texts:
        return ViewInventoryEntry(
            crop_id=crop_id,
            view=ViewHypothesis.LABEL,
            confidence=0.62,
            fact_class=FactClass.INFERRED,
        )
    if "box" in texts or "packaging" in texts:
        return ViewInventoryEntry(
            crop_id=crop_id,
            view=ViewHypothesis.BOX,
            confidence=0.45,
            fact_class=FactClass.INFERRED,
        )
    # Worn: tall frame, subject in the lower half, modest subject area.
    _x, y, _w, h = region
    lower = parent_height > 0 and (y + h) / parent_height > 0.7
    if parent_height > 0 and aspect < 0.85 and lower and subject_area < 0.45:
        return ViewInventoryEntry(
            crop_id=crop_id,
            view=ViewHypothesis.WORN,
            confidence=0.48,
            fact_class=FactClass.INFERRED,
        )
    if 0.85 <= aspect <= 1.15 and subject_area > 0.4:
        return ViewInventoryEntry(
            crop_id=crop_id,
            view=ViewHypothesis.TOP,
            confidence=0.4,
            fact_class=FactClass.INFERRED,
        )
    if aspect > 1.6 and subject_area > 0.35:
        return ViewInventoryEntry(
            crop_id=crop_id,
            view=ViewHypothesis.SOLE,
            confidence=0.38,
            fact_class=FactClass.INFERRED,
        )
    if 1.15 < aspect <= 1.7:
        return ViewInventoryEntry(
            crop_id=crop_id,
            view=ViewHypothesis.LATERAL,
            confidence=0.44,
            fact_class=FactClass.INFERRED,
        )
    if aspect < 0.75:
        return ViewInventoryEntry(
            crop_id=crop_id,
            view=ViewHypothesis.HEEL,
            confidence=0.36,
            fact_class=FactClass.INFERRED,
        )
    if min(width, height) < 180:
        return ViewInventoryEntry(
            crop_id=crop_id,
            view=ViewHypothesis.DETAIL,
            confidence=0.4,
            fact_class=FactClass.INFERRED,
        )
    return ViewInventoryEntry(
        crop_id=crop_id,
        view=ViewHypothesis.UNKNOWN,
        confidence=0.25,
        fact_class=FactClass.INFERRED,
    )
