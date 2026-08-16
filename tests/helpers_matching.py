"""Builders for matching / authenticity tests. No flagship answers."""

from __future__ import annotations

from decimal import Decimal

from searcher.contracts.enums import Availability, FactClass, FactOrigin, ImageRole
from searcher.contracts.models import (
    ItemHypothesis,
    ListingCandidate,
    ListingImage,
    SearchConstraints,
    VisualSignature,
)
from searcher.contracts.primitives import classified
from searcher.core.ids import new_id, sha256_hex
from searcher.core.time import parse_utc
from searcher.hypotheses.beliefs import empty_belief, make_belief
from searcher.matching.synth import ShoeSpec, render_views

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def make_hypothesis(
    *,
    search_id: str | None = None,
    text: str = "House Name Field Model 07",
    category: str = "footwear",
    colour: str | None = None,
) -> ItemHypothesis:
    empty = empty_belief()
    return ItemHypothesis(
        hypothesis_id=new_id(),
        search_id=search_id or new_id(),
        category=category,
        brand=make_belief(
            "House Name",
            confidence=0.6,
            fact_class=FactClass.USER_SUPPLIED,
            origin=FactOrigin.USER,
        ),
        model_name=make_belief(
            "Field Model",
            confidence=0.55,
            fact_class=FactClass.USER_SUPPLIED,
            origin=FactOrigin.USER,
        ),
        line=empty,
        designer=empty,
        season=empty,
        year=make_belief(
            "2007",
            confidence=0.4,
            fact_class=FactClass.USER_SUPPLIED,
            origin=FactOrigin.USER,
        ),
        colourway=make_belief(
            colour,
            confidence=0.4 if colour else 0.0,
            fact_class=FactClass.USER_SUPPLIED,
            origin=FactOrigin.USER,
        )
        if colour
        else empty,
        visual_signature=VisualSignature(ocr_terms=["Field", "Model"]),
        posterior=0.55,
    )


def make_candidate(
    *,
    candidate_id: str | None = None,
    url: str = "https://fixture.local/item/1",
    title: str = "House Name Field Model 07",
    description: str = "Lateral, heel, sole and label photographs.",
    availability: Availability = Availability.LIVE,
    images: list[tuple[str, bytes, ImageRole]] | None = None,
    seller_metadata: dict[str, object] | None = None,
    price: str = "800.00",
    cluster_id: str | None = None,
) -> tuple[ListingCandidate, dict[str, bytes]]:
    pngs: dict[str, bytes] = {}
    listing_images: list[ListingImage] = []
    cid = candidate_id or new_id()
    for name, data, role in images or []:
        lid = f"{cid}-{name}"
        digest = sha256_hex(data)
        pngs[lid] = data
        listing_images.append(
            ListingImage(
                listing_image_id=lid,
                candidate_id=cid,
                remote_url=f"{url}/{name}.png",
                content_digest=digest,
                perceptual_hash=digest[:16],
                width=480,
                height=280,
                role=role,
                duplicate_family_id=digest[:16],
            )
        )
    candidate = ListingCandidate(
        candidate_id=cid,
        canonical_url=url,
        source_adapter="fixture",
        source_listing_id=cid,
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        description=classified(description, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        seller_reported_brand=classified(
            "House Name", FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER
        ),
        seller_reported_model=classified(
            "Field Model", FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER
        ),
        price_original=Decimal(price),
        currency_original="EUR",
        size_original="42",
        availability=availability,
        seller_metadata=seller_metadata or {},
        images=listing_images,
        first_seen_at=_TS,
        last_checked_at=_TS,
        cluster_id=cluster_id,
    )
    return candidate, pngs


def views_for(spec: ShoeSpec) -> list[tuple[str, bytes, ImageRole]]:
    rendered = render_views(spec)
    roles = {
        "lateral": ImageRole.PRODUCT,
        "heel": ImageRole.PRODUCT,
        "sole": ImageRole.SOLE,
        "label": ImageRole.LABEL,
        "front": ImageRole.PRODUCT,
    }
    return [(name, rendered[name], roles[name]) for name in rendered]


def constraints(*, colour: str | None = None) -> SearchConstraints:
    return SearchConstraints(category="footwear", brand="House Name", colour=colour, size="42")
