"""Evidence promotion rules. Later waves add decode/magic checks."""

from __future__ import annotations

from enum import StrEnum

from searcher.core.errors import InvariantViolation
from searcher.evidence.content_store import ZONES, ContentStore


class PromotionDecision(StrEnum):
    PROMOTED = "promoted"
    HELD = "held"
    REFUSED = "refused"


_ALLOWED = {
    ("incoming", "quarantine"),
    ("incoming", "verified"),
    ("incoming", "derived"),
    ("quarantine", "verified"),
    ("verified", "derived"),
    ("derived", "exports"),
    ("incoming", "temporary"),
    ("temporary", "quarantine"),
}


def promote(
    store: ContentStore,
    digest: str,
    *,
    from_zone: str,
    to_zone: str,
    search_id: str,
    accepted: bool,
) -> PromotionDecision:
    """Promote an object between §27.3 zones under explicit rules."""
    if from_zone not in ZONES or to_zone not in ZONES:
        raise InvariantViolation(f"unknown zone {from_zone!r} -> {to_zone!r}")
    if (from_zone, to_zone) not in _ALLOWED:
        return PromotionDecision.REFUSED
    if to_zone == "verified" and not accepted:
        return PromotionDecision.HELD
    if not store.exists(digest):
        return PromotionDecision.REFUSED
    if not store.owned_by(digest, search_id):
        raise InvariantViolation(
            "cannot promote another campaign's artifact",
            search_id=search_id,
        )
    store.link_zone(digest, to_zone)
    return PromotionDecision.PROMOTED
