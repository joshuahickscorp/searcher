"""Fine matching: isolation, parts, correspondence, geometry, explanations."""

from __future__ import annotations

from searcher.matching.ontology import (
    FOOTWEAR_ONTOLOGY,
    GARMENT_ONTOLOGY,
    CategoryOntology,
    ontology_for,
    register_ontology,
)
from searcher.matching.pipeline import enrich_candidate, match_candidate, prepare_reference

__all__ = [
    "FOOTWEAR_ONTOLOGY",
    "GARMENT_ONTOLOGY",
    "CategoryOntology",
    "enrich_candidate",
    "match_candidate",
    "ontology_for",
    "prepare_reference",
    "register_ontology",
]
