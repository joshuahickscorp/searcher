"""Category-specific part ontologies. Footwear first; garments add a profile."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PartSpec:
    name: str
    views: tuple[str, ...]
    authenticity_critical: bool = False
    geometry_role: str = "region"
    countable: bool = False


@dataclass(frozen=True, slots=True)
class CategoryOntology:
    category: str
    profile_id: str
    parts: tuple[PartSpec, ...]
    expected_views: tuple[str, ...]
    authenticity_critical_views: tuple[str, ...]
    relational_checks: tuple[str, ...]

    def part_names(self) -> tuple[str, ...]:
        return tuple(part.name for part in self.parts)

    def parts_for_view(self, view: str) -> tuple[PartSpec, ...]:
        return tuple(part for part in self.parts if view in part.views)

    def critical_parts(self) -> tuple[PartSpec, ...]:
        return tuple(part for part in self.parts if part.authenticity_critical)


FOOTWEAR_ONTOLOGY = CategoryOntology(
    category="footwear",
    profile_id="designer_footwear",
    parts=(
        PartSpec("toe_box", ("front", "lateral", "medial", "top"), True, "region"),
        PartSpec("vamp", ("front", "top", "lateral"), True, "region"),
        PartSpec("tongue", ("top", "front", "tongue"), True, "region"),
        PartSpec("eye_stay", ("top", "lateral", "front"), False, "region"),
        PartSpec("eyelets", ("top", "lateral", "front"), True, "count", True),
        PartSpec("laces", ("top", "front"), False, "region"),
        PartSpec("lateral_panels", ("lateral",), True, "count", True),
        PartSpec("medial_panels", ("medial",), True, "count", True),
        PartSpec("heel", ("heel", "rear", "lateral", "medial"), True, "region"),
        PartSpec("outsole", ("sole", "lateral", "medial"), True, "region"),
        PartSpec("midsole", ("lateral", "medial", "sole"), False, "region"),
        PartSpec("tread", ("sole",), True, "region"),
        PartSpec("logo", ("lateral", "medial", "heel", "detail"), True, "mark"),
        PartSpec("label", ("label", "tongue", "detail"), True, "mark"),
        PartSpec("hardware", ("detail", "top", "lateral"), False, "count", True),
        PartSpec("seams", ("lateral", "medial", "heel"), True, "count", True),
        PartSpec("material_boundaries", ("lateral", "medial", "detail"), False, "region"),
    ),
    expected_views=(
        "lateral",
        "medial",
        "front",
        "heel",
        "sole",
        "tongue",
        "label",
        "size",
        "hardware",
    ),
    authenticity_critical_views=("lateral", "heel", "sole", "label"),
    relational_checks=(
        "sole_to_upper",
        "heel_angle",
        "panel_intersection",
        "aspect_ratio",
        "part_count",
        "relative_part_position",
    ),
)


GARMENT_ONTOLOGY = CategoryOntology(
    category="garment",
    profile_id="designer_garment",
    parts=(
        PartSpec("collar", ("front", "rear", "detail"), True, "region"),
        PartSpec("placket", ("front",), True, "region"),
        PartSpec("sleeve", ("lateral", "front"), False, "region"),
        PartSpec("cuff", ("detail", "lateral"), False, "region"),
        PartSpec("hem", ("front", "rear"), False, "region"),
        PartSpec("pocket", ("front", "lateral"), False, "count", True),
        PartSpec("closure", ("front", "detail"), True, "count", True),
        PartSpec("lining", ("detail", "label"), False, "material"),
        PartSpec("label", ("label", "detail"), True, "mark"),
        PartSpec("logo", ("front", "detail"), True, "mark"),
        PartSpec("seams", ("front", "rear", "lateral"), True, "count", True),
        PartSpec("yoke", ("rear", "front"), False, "region"),
    ),
    expected_views=("front", "rear", "lateral", "label", "detail"),
    authenticity_critical_views=("front", "label", "detail"),
    relational_checks=("panel_intersection", "aspect_ratio", "part_count"),
)


_REGISTRY: dict[str, CategoryOntology] = {
    "footwear": FOOTWEAR_ONTOLOGY,
    "designer_footwear": FOOTWEAR_ONTOLOGY,
    "sneaker": FOOTWEAR_ONTOLOGY,
    "trainer": FOOTWEAR_ONTOLOGY,
    "shoe": FOOTWEAR_ONTOLOGY,
    "garment": GARMENT_ONTOLOGY,
    "designer_garment": GARMENT_ONTOLOGY,
    "clothing": GARMENT_ONTOLOGY,
    "outerwear": GARMENT_ONTOLOGY,
    "top": GARMENT_ONTOLOGY,
    "bottom": GARMENT_ONTOLOGY,
    "shirt": GARMENT_ONTOLOGY,
    "shirts": GARMENT_ONTOLOGY,
    "long-sleeve": GARMENT_ONTOLOGY,
    "longsleeve": GARMENT_ONTOLOGY,
    "long_sleeve": GARMENT_ONTOLOGY,
    "cutsew": GARMENT_ONTOLOGY,
}


def ontology_for(category: str | None) -> CategoryOntology:
    if not category:
        return FOOTWEAR_ONTOLOGY
    key = category.strip().lower()
    if key in _REGISTRY:
        return _REGISTRY[key]
    # Unknown category: do not silently apply footwear rules.
    return CategoryOntology(
        category=key,
        profile_id=f"generic:{key}",
        parts=(PartSpec("subject", ("unknown",), False, "region"),),
        expected_views=("unknown",),
        authenticity_critical_views=(),
        relational_checks=("aspect_ratio", "silhouette"),
    )


def register_ontology(ontology: CategoryOntology) -> None:
    """Add a profile without rewriting the matcher."""
    _REGISTRY[ontology.category] = ontology
    _REGISTRY[ontology.profile_id] = ontology
