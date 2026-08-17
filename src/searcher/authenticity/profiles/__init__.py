"""Category authenticity profiles."""

from __future__ import annotations

from searcher.authenticity.profiles.base import CategoryProfile, generic_profile
from searcher.authenticity.profiles.footwear import FOOTWEAR_PROFILE
from searcher.authenticity.profiles.garment import GARMENT_PROFILE

_PROFILES: dict[str, CategoryProfile] = {
    "footwear": FOOTWEAR_PROFILE,
    "designer_footwear": FOOTWEAR_PROFILE,
    "sneaker": FOOTWEAR_PROFILE,
    "trainer": FOOTWEAR_PROFILE,
    "shoe": FOOTWEAR_PROFILE,
    "garment": GARMENT_PROFILE,
    "designer_garment": GARMENT_PROFILE,
    "clothing": GARMENT_PROFILE,
    "outerwear": GARMENT_PROFILE,
    "top": GARMENT_PROFILE,
    "bottom": GARMENT_PROFILE,
    "shirt": GARMENT_PROFILE,
    "shirts": GARMENT_PROFILE,
    "long-sleeve": GARMENT_PROFILE,
    "longsleeve": GARMENT_PROFILE,
    "long_sleeve": GARMENT_PROFILE,
    "cutsew": GARMENT_PROFILE,
}


def profile_for(category: str | None) -> CategoryProfile:
    if not category:
        return generic_profile("unknown")
    key = category.strip().lower()
    if key.startswith("generic:"):
        key = key.split(":", 1)[1]
    if key in _PROFILES:
        return _PROFILES[key]
    return generic_profile(key)


__all__ = [
    "CategoryProfile",
    "FOOTWEAR_PROFILE",
    "GARMENT_PROFILE",
    "generic_profile",
    "profile_for",
]
