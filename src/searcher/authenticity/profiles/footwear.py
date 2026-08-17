"""designer_footwear authenticity profile (§19.7). Data, not matcher code."""

from __future__ import annotations

from searcher.authenticity.profiles.base import CategoryProfile

FOOTWEAR_PROFILE = CategoryProfile(
    profile_id="designer_footwear",
    category="footwear",
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
    critical_views=("lateral", "heel", "sole", "label"),
    label_rules=("code_format", "period_layout", "size_block"),
    construction_checks=(
        "panel_count",
        "eyelet_count",
        "heel_construction",
        "outsole_geometry",
        "tongue",
        "stitch_regularity",
    ),
    material_checks=("colour_after_lighting", "surface_smoothness"),
    provenance_signals=("box", "dust_bag", "receipt"),
    established_parts=(
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
    ),
)
