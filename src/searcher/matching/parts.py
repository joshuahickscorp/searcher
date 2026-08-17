"""§18.4 part extraction driven by the category ontology."""

from __future__ import annotations

from searcher.contracts.primitives import PartMatch
from searcher.matching.ontology import CategoryOntology, PartSpec
from searcher.matching.structure import extract_structure
from searcher.matching.types import (
    CorrespondenceResult,
    ExtractedPart,
    IsolatedSubject,
    StructuredDescriptor,
    ViewGuess,
)


def extract_parts(
    *,
    ontology: CategoryOntology,
    subjects: list[IsolatedSubject],
    views: list[ViewGuess],
    descriptors: dict[str, StructuredDescriptor],
) -> list[ExtractedPart]:
    by_id = {item.image_id: item for item in subjects}
    parts: list[ExtractedPart] = []
    for guess in views:
        subject = by_id.get(guess.image_id)
        if subject is None or not subject.relevant:
            continue
        desc = descriptors.get(guess.image_id)
        view_name = guess.view.value
        for spec in ontology.parts_for_view(view_name):
            parts.append(_from_spec(spec, guess, desc))
    return parts


def _from_spec(
    spec: PartSpec, guess: ViewGuess, desc: StructuredDescriptor | None
) -> ExtractedPart:
    count: int | None = None
    region: tuple[float, float, float, float] | None = None
    descriptor: str | None = None
    confidence = 0.35 * guess.confidence
    notes: list[str] = []
    if desc is None:
        notes.append("no_structure")
        return ExtractedPart(
            spec.name, guess.image_id, guess.view.value, None, None, None, 0.2, notes
        )
    if spec.name == "eyelets":
        count = desc.eyelet_count
        confidence = 0.7 if count else 0.25
    elif spec.name in {"lateral_panels", "medial_panels"}:
        count = desc.panel_count
        confidence = 0.65 if count else 0.25
    elif spec.name == "seams":
        count = desc.seam_count
        confidence = 0.6
    elif spec.name == "outsole":
        descriptor = f"ratio={desc.outsole_ratio:.3f}"
        confidence = 0.6
    elif spec.name == "tread":
        descriptor = desc.tread_kind
        confidence = 0.55
    elif spec.name == "heel":
        descriptor = f"{desc.heel_cut}:{desc.heel_angle:.3f}"
        confidence = 0.58
    elif spec.name == "logo":
        if desc.logo_xy:
            region = (desc.logo_xy[0], desc.logo_xy[1], 0.08, 0.08)
            descriptor = desc.logo_kind
            confidence = 0.62
        else:
            notes.append("logo_not_found")
            confidence = 0.2
    elif spec.name == "label":
        descriptor = desc.label_hash
        confidence = 0.55 if desc.label_hash else 0.2
    else:
        confidence = 0.4
    return ExtractedPart(
        name=spec.name,
        image_id=guess.image_id,
        view=guess.view.value,
        count=count,
        region=region,
        descriptor=descriptor,
        confidence=round(confidence, 4),
        notes=notes,
    )


def build_descriptors(subjects: list[IsolatedSubject]) -> dict[str, StructuredDescriptor]:
    out: dict[str, StructuredDescriptor] = {}
    for subject in subjects:
        if not subject.relevant:
            continue
        out[subject.image_id] = extract_structure(subject.png, image_id=subject.image_id)
    return out


def compare_extracted_parts(
    *,
    ontology: CategoryOntology,
    candidate_parts: list[ExtractedPart],
    correspondence: CorrespondenceResult | None,
    strong_inliers: int,
) -> list[PartMatch]:
    """Score ontology parts. Correspondence is identity; extraction is presence.

    Footwear construction counts (eyelets, outsole) are a different function.
    A shirt must not inherit a 0.95 because both sides had zero eyelets.
    """
    from searcher.matching.combine import make_part_match

    allowed = set(ontology.part_names())
    names: list[str] = []
    confidence_by_name: dict[str, float] = {}
    for part in candidate_parts:
        if part.name not in allowed:
            continue
        if part.name not in names:
            names.append(part.name)
        confidence_by_name[part.name] = max(confidence_by_name.get(part.name, 0.0), part.confidence)
    strong = correspondence is not None and correspondence.inlier_count >= strong_inliers
    corr_ref = (
        f"{correspondence.method}:{correspondence.inlier_count}"
        if correspondence is not None and strong
        else None
    )
    if not names:
        if strong and corr_ref is not None:
            return [
                make_part_match(
                    "subject",
                    0.95,
                    explanation=f"correspondence {corr_ref}-inliers",
                    correspondence_ref=corr_ref,
                )
            ]
        return []
    records: list[PartMatch] = []
    for name in names:
        if strong and corr_ref is not None:
            records.append(
                make_part_match(
                    name,
                    0.95,
                    explanation=f"correspondence {corr_ref}-inliers",
                    correspondence_ref=corr_ref,
                )
            )
        else:
            conf = confidence_by_name[name]
            records.append(
                make_part_match(
                    name,
                    max(0.35, min(0.55, conf)),
                    explanation="extracted-unconfirmed",
                )
            )
    return records
