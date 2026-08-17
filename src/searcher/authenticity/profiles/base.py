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
    established_parts: tuple[str, ...] = ()


# Views any photographed object can plausibly show, drawn from ViewHypothesis.
# The generic profile used to expect a view literally named "unknown", which no
# listing can supply, so coverage was always 0 and completeness was pinned at
# 0.6*0 + 0.4*1 = 0.4 for every category without a profile of its own. Nothing
# outside footwear could clear an authenticity gate above 0.4, which is why a
# garment could never reach Real however good the match was.
_GENERIC_EXPECTED_VIEWS = ("front", "rear", "detail", "label")


def generic_profile(category: str) -> CategoryProfile:
    return CategoryProfile(
        profile_id=f"generic:{category}",
        category=category,
        expected_views=_GENERIC_EXPECTED_VIEWS,
        # No critical view: for a category we have no profile for, we do not
        # know which single photograph would settle it, and inventing one would
        # be a claim we cannot support.
        critical_views=(),
        label_rules=(),
        construction_checks=("silhouette",),
        material_checks=(),
        provenance_signals=(),
    )
