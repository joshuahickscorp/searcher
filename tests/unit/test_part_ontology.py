"""Part ontology is category-specific and garment-extensible."""

from __future__ import annotations

from searcher.matching.ontology import (
    FOOTWEAR_ONTOLOGY,
    GARMENT_ONTOLOGY,
    CategoryOntology,
    PartSpec,
    ontology_for,
    register_ontology,
)


def test_footwear_has_bible_parts() -> None:
    names = set(FOOTWEAR_ONTOLOGY.part_names())
    for required in (
        "toe_box",
        "vamp",
        "tongue",
        "eye_stay",
        "eyelets",
        "laces",
        "lateral_panels",
        "medial_panels",
        "heel",
        "outsole",
        "midsole",
        "tread",
        "logo",
        "label",
        "hardware",
        "seams",
        "material_boundaries",
    ):
        assert required in names


def test_garment_profile_exists_without_rewriting_matcher() -> None:
    assert "collar" in GARMENT_ONTOLOGY.part_names()
    assert ontology_for("garment") is GARMENT_ONTOLOGY
    assert ontology_for("watch").profile_id.startswith("generic:")
    assert ontology_for("watch").parts[0].name == "subject"


def test_register_new_profile() -> None:
    bag = CategoryOntology(
        category="bag",
        profile_id="designer_bag",
        parts=(PartSpec("handle", ("front",), True, "region"),),
        expected_views=("front", "label"),
        authenticity_critical_views=("label",),
        relational_checks=("aspect_ratio",),
    )
    register_ontology(bag)
    assert ontology_for("bag").profile_id == "designer_bag"


def test_parts_for_view() -> None:
    lateral = FOOTWEAR_ONTOLOGY.parts_for_view("lateral")
    assert any(part.name == "lateral_panels" for part in lateral)
    assert not any(part.name == "medial_panels" for part in lateral)
