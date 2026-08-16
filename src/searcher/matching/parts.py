"""§18.4 part extraction driven by the category ontology."""

from __future__ import annotations

from searcher.matching.ontology import CategoryOntology, PartSpec
from searcher.matching.structure import extract_structure
from searcher.matching.types import ExtractedPart, IsolatedSubject, StructuredDescriptor, ViewGuess


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
