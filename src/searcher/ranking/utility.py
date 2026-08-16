"""LISTING_UTILITY. Independent of match and authenticity."""

from __future__ import annotations

from searcher.contracts.enums import Availability
from searcher.contracts.models import ListingCandidate, ListingUtility, SearchConstraints
from searcher.contracts.primitives import PublicExplanation
from searcher.core.time import utc_now


def listing_utility(
    candidate: ListingCandidate,
    *,
    constraints: SearchConstraints | None = None,
    destination_verified: bool = False,
) -> ListingUtility:
    live = candidate.availability is Availability.LIVE
    size_match = None
    if constraints and constraints.size and candidate.size_original:
        size_match = 1.0 if constraints.size.lower() in candidate.size_original.lower() else 0.2
    region_match = None
    if constraints and constraints.region:
        region_match = 0.5
    price_fit = None
    if constraints and constraints.price_max and candidate.price_original is not None:
        price_fit = 1.0 if candidate.price_original <= constraints.price_max else 0.2
    coverage = min(1.0, len(candidate.images) / 4.0)
    desc_q = 0.6 if candidate.description and candidate.description.value else 0.25
    score = 0.0
    score += 0.45 if live else 0.0
    score += 0.15 * (size_match or 0.5)
    score += 0.1 * (region_match or 0.5)
    score += 0.1 * coverage
    score += 0.1 * desc_q
    score += 0.1 if destination_verified else 0.0
    return ListingUtility(
        live=live,
        size_match=size_match,
        region_match=region_match,
        condition_match=None,
        price_fit=price_fit,
        shipping_known=False,
        description_quality=desc_q,
        image_coverage=coverage,
        last_checked_at=candidate.last_checked_at or utc_now(),
        utility_score=max(0.0, min(1.0, score)),
        explanation=PublicExplanation(
            live_status=candidate.availability,
            last_checked_at=candidate.last_checked_at,
            seller_reported_fields=["title"] if candidate.title else [],
        ),
    )
