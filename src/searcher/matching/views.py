"""View classification for listing images. Labels stay probabilistic."""

from __future__ import annotations

from collections.abc import Mapping

from searcher.contracts.enums import ImageRole, ViewHypothesis
from searcher.matching.types import IsolatedSubject, StructuredDescriptor, ViewGuess
from searcher.reference.views import classify_view


def classify_listing_view(
    subject: IsolatedSubject, *, ocr_kinds: set[str] | None = None
) -> ViewGuess:
    kinds = ocr_kinds or set()
    role = subject.role
    if role == ImageRole.LABEL.value or "label" in kinds or "size" in kinds:
        return ViewGuess(subject.image_id, ViewHypothesis.LABEL, 0.7, "role_or_ocr")
    if role == ImageRole.SOLE.value:
        return ViewGuess(subject.image_id, ViewHypothesis.SOLE, 0.72, "role")
    if role == ImageRole.PRODUCT.value:
        aspect = (subject.width or 1) / max(1, subject.height)
        if 1.05 <= aspect <= 2.4:
            return ViewGuess(subject.image_id, ViewHypothesis.LATERAL, 0.55, "product_role")
        if aspect < 1.05:
            return ViewGuess(subject.image_id, ViewHypothesis.HEEL, 0.5, "product_role")
    x, y, w, h = subject.bbox
    parent_w = max(subject.width or w, 1)
    parent_h = max(subject.height or h, 1)
    entry = classify_view(
        crop_id=subject.image_id,
        width=w,
        height=h,
        region=(float(x), float(y), float(w), float(h)),
        parent_width=parent_w,
        parent_height=parent_h,
        ocr=[],
        subject_area=subject.subject_area,
    )
    return ViewGuess(subject.image_id, entry.view, entry.confidence, "geometry")


def classify_subjects(subjects: list[IsolatedSubject]) -> list[ViewGuess]:
    return [classify_listing_view(item) for item in subjects]


def refine_views(
    guesses: list[ViewGuess],
    descriptors: Mapping[str, StructuredDescriptor],
) -> list[ViewGuess]:
    """Upgrade guesses using extracted structure. Still probabilistic."""
    out: list[ViewGuess] = []
    for guess in guesses:
        desc = descriptors.get(guess.image_id)
        if desc is None:
            out.append(guess)
            continue
        view = guess.view
        confidence = guess.confidence
        if desc.label_hash:
            view, confidence = ViewHypothesis.LABEL, max(confidence, 0.72)
        elif desc.eyelet_count >= 3 and desc.panel_count >= 2:
            view, confidence = ViewHypothesis.LATERAL, max(confidence, 0.7)
        elif desc.eyelet_count == 0:
            if desc.aspect >= 1.8:
                view, confidence = ViewHypothesis.SOLE, max(confidence, 0.66)
            else:
                view, confidence = ViewHypothesis.HEEL, max(confidence, 0.6)
        out.append(ViewGuess(guess.image_id, view, confidence, "structure_refine"))
    return out
