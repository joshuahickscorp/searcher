"""Which authenticity fields a category is allowed to publish.

Footwear construction (eyelets, outsole, heel) is a measurement only for the
footwear profile. Repeating those part names on a shirt is a claim the engine
cannot support. Non-footwear categories either publish garment-appropriate
parts they actually measured, or mark the field unestablished.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from searcher.authenticity.profiles.base import CategoryProfile

UNESTABLISHED_PREFIX = "unestablished:"
UNESTABLISHED_CONSTRUCTION = f"{UNESTABLISHED_PREFIX}construction"

# Construction checks the engine can actually score from StructuredDescriptor.
MEASURABLE_CONSTRUCTION = frozenset(
    {
        "panel_count",
        "eyelet_count",
        "heel_construction",
        "outsole_geometry",
        "tongue",
    }
)

_FOOTWEAR_CATEGORIES = frozenset(
    {
        "footwear",
        "designer_footwear",
        "sneaker",
        "trainer",
        "shoe",
    }
)

# Tokens that are footwear part or view evidence. A garment listing must never
# publish these names: saying "heel is unestablished" still reports a heel.
_FOOTWEAR_ONLY_TOKENS = frozenset(
    {
        "eyelet",
        "eyelets",
        "eyestay",
        "outsole",
        "midsole",
        "tread",
        "heel",
        "tongue",
        "vamp",
        "toebox",
        "laces",
        "lace",
        "medial",
        "medialpanels",
        "lateralpanels",
    }
)

_TOKEN = re.compile(r"[a-z0-9]+")


def footwear_rules_apply(category_or_profile: str | None) -> bool:
    if not category_or_profile:
        return False
    key = category_or_profile.strip().lower()
    if key.startswith("generic:"):
        key = key.split(":", 1)[1]
    return key in _FOOTWEAR_CATEGORIES


def construction_is_established(profile: CategoryProfile) -> bool:
    return any(check in MEASURABLE_CONSTRUCTION for check in profile.construction_checks)


def unestablished_field_names(profile: CategoryProfile) -> tuple[str, ...]:
    if construction_is_established(profile):
        return ()
    return ("construction",)


def unestablished_tokens(profile: CategoryProfile) -> list[str]:
    return [f"{UNESTABLISHED_PREFIX}{name}" for name in unestablished_field_names(profile)]


def _tokens(text: str) -> set[str]:
    folded = text.lower().replace("_", " ").replace("-", " ")
    return set(_TOKEN.findall(folded))


def mentions_footwear_only_part(text: str) -> bool:
    tokens = _tokens(text)
    if tokens & _FOOTWEAR_ONLY_TOKENS:
        return True
    compact = "".join(tokens)
    if "lateralpanels" in compact or "medialpanels" in compact or "eyestay" in compact:
        return True
    if "wrong" in tokens and "last" in tokens:
        return True
    return "sole" in tokens and "absolute" not in tokens


def is_established_claim(text: str, profile: CategoryProfile) -> bool:
    if text.startswith(UNESTABLISHED_PREFIX):
        return True
    if footwear_rules_apply(profile.category) or footwear_rules_apply(profile.profile_id):
        return True
    return not mentions_footwear_only_part(text)


def established_claims(items: Iterable[str], profile: CategoryProfile) -> list[str]:
    return [item for item in items if is_established_claim(item, profile)]


def published_compare_parts(
    part_names: Iterable[str],
    profile: CategoryProfile,
) -> list[dict[str, str]]:
    """Compare-view rows a user is allowed to see for this category."""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in part_names:
        if not name or name in seen:
            continue
        if not is_established_claim(name, profile):
            continue
        seen.add(name)
        rows.append({"part": name, "status": "compared"})
    for field in unestablished_field_names(profile):
        if field in seen:
            continue
        seen.add(field)
        rows.append(
            {
                "part": field,
                "status": "unestablished",
                "note": "not established for this category",
            }
        )
    return rows
