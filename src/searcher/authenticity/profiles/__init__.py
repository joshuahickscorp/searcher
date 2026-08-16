"""Category authenticity profiles."""

from __future__ import annotations

from searcher.authenticity.profiles.base import CategoryProfile, generic_profile
from searcher.authenticity.profiles.footwear import FOOTWEAR_PROFILE

_PROFILES: dict[str, CategoryProfile] = {
    "footwear": FOOTWEAR_PROFILE,
    "designer_footwear": FOOTWEAR_PROFILE,
    "sneaker": FOOTWEAR_PROFILE,
    "trainer": FOOTWEAR_PROFILE,
}


def profile_for(category: str | None) -> CategoryProfile:
    if not category:
        return generic_profile("unknown")
    key = category.strip().lower()
    if key in _PROFILES:
        return _PROFILES[key]
    return generic_profile(key)


__all__ = ["CategoryProfile", "FOOTWEAR_PROFILE", "generic_profile", "profile_for"]
