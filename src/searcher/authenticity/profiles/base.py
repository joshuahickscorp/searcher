"""Category profile protocol. Footwear rules must not apply to other categories."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CategoryProfile:
    profile_id: str
    category: str
    expected_views: tuple[str, ...]
    critical_views: tuple[str, ...]
    label_rules: tuple[str, ...]
    construction_checks: tuple[str, ...]
    material_checks: tuple[str, ...]
    provenance_signals: tuple[str, ...]


def generic_profile(category: str) -> CategoryProfile:
    return CategoryProfile(
        profile_id=f"generic:{category}",
        category=category,
        expected_views=("unknown",),
        critical_views=(),
        label_rules=(),
        construction_checks=("silhouette",),
        material_checks=(),
        provenance_signals=(),
    )
