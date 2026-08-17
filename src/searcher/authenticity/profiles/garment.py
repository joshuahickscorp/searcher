"""designer_garment authenticity profile. Views only; no invented construction."""

from __future__ import annotations

from searcher.authenticity.profiles.base import CategoryProfile

# Views match what the garment ontology and view classifier can actually emit.
# Construction is empty: the engine has no collar/placket/seam measurement, and
# scoring eyelets or outsole for a shirt would be a claim we cannot support.
GARMENT_PROFILE = CategoryProfile(
    profile_id="designer_garment",
    category="garment",
    expected_views=("front", "rear", "lateral", "label", "detail"),
    critical_views=("front", "label", "detail"),
    label_rules=("code_format",),
    construction_checks=(),
    material_checks=("colour_after_lighting", "surface_smoothness"),
    provenance_signals=("receipt", "hang_tag"),
    established_parts=(
        "collar",
        "placket",
        "sleeve",
        "cuff",
        "hem",
        "pocket",
        "closure",
        "lining",
        "label",
        "logo",
        "seams",
        "yoke",
    ),
)
