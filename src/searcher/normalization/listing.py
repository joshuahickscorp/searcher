"""Map a RawListing into ListingCandidate. Originals are always kept."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from searcher.contracts.enums import (
    Availability,
    ExtractionMethod,
    FactClass,
    FactOrigin,
    ImageRole,
)
from searcher.contracts.models import ListingCandidate, ListingImage, RawListing
from searcher.contracts.primitives import ClassifiedFact, NormalizedField, PublicExplanation
from searcher.core.ids import new_id, sha256_hex
from searcher.normalization.currency import parse_price
from searcher.normalization.fields import extracted, seller_reported
from searcher.normalization.size import parse_size
from searcher.normalization.url import canonicalize_url, extract_listing_id


def _fact(value: object | None, *, seller: bool) -> ClassifiedFact | None:
    if value is None or value == "":
        return None
    if seller:
        return ClassifiedFact(
            value=value if isinstance(value, str | int | float | bool) else str(value),
            fact_class=FactClass.REPORTED_BY_SELLER,
            origin=FactOrigin.SELLER,
        )
    return ClassifiedFact(
        value=value if isinstance(value, str | int | float | bool) else str(value),
        fact_class=FactClass.EXTRACTED,
        origin=FactOrigin.EXTRACTOR,
    )


def _availability(raw: str | None) -> Availability:
    if not raw:
        return Availability.UNKNOWN
    text = raw.strip().upper()
    mapping = {
        "LIVE": Availability.LIVE,
        "INSTOCK": Availability.LIVE,
        "IN_STOCK": Availability.LIVE,
        "HTTPS://SCHEMA.ORG/INSTOCK": Availability.LIVE,
        "SOLD": Availability.SOLD,
        "SOLDOUT": Availability.SOLD,
        "OUTOFSTOCK": Availability.SOLD,
        "HTTPS://SCHEMA.ORG/SOLDOUT": Availability.SOLD,
        "HTTPS://SCHEMA.ORG/OUTOFSTOCK": Availability.SOLD,
        "RESERVED": Availability.RESERVED,
        "PENDING": Availability.RESERVED,
        "REMOVED": Availability.REMOVED,
        "DISCONTINUED": Availability.REMOVED,
        "UNKNOWN": Availability.UNKNOWN,
    }
    if text in mapping:
        return mapping[text]
    lowered = raw.lower()
    sold_needles = (
        "sold",
        "ended",
        "売り切れ",
        "売却済",
        "落札済",
        "판매완료",
        "已售",
        "vendu",
        "venduto",
        "продано",
    )
    reserved_needles = ("reserved", "取引中", "예약", "réservé", "riservato")
    if any(n in lowered for n in sold_needles):
        return Availability.SOLD
    if any(n in lowered for n in reserved_needles):
        return Availability.RESERVED
    return Availability.UNKNOWN


def normalize_raw(raw: RawListing, *, search_id: str | None = None) -> ListingCandidate:
    del search_id
    payload = raw.payload
    url = str(payload.get("canonical_url") or raw.url)
    canon = canonicalize_url(url)
    title = payload.get("title")
    description = payload.get("description")
    brand = payload.get("brand")
    model = payload.get("model")
    price_raw = payload.get("price_original")
    currency_raw = payload.get("currency")
    size_raw = payload.get("size")
    avail_raw = payload.get("availability")
    method = ExtractionMethod(str(payload.get("extraction_method") or "unknown"))
    region = str(payload.get("source_region") or "") or None
    parsed_price = parse_price(
        str(price_raw) if price_raw is not None else None,
        str(currency_raw) if currency_raw else None,
    )
    parsed_size = parse_size(str(size_raw) if size_raw is not None else None)
    availability = _availability(str(avail_raw) if avail_raw is not None else None)
    now = raw.fetched_at
    images: list[ListingImage] = []
    candidate_id = new_id()
    images_raw = payload.get("images") or []
    if not isinstance(images_raw, list):
        images_raw = []
    for image in images_raw:
        if not isinstance(image, dict):
            continue
        remote = str(image.get("url") or "")
        if not remote:
            continue
        digest = image.get("digest")
        images.append(
            ListingImage(
                listing_image_id=new_id(),
                candidate_id=candidate_id,
                remote_url=remote,
                content_digest=str(digest) if digest else None,
                perceptual_hash=(
                    image.get("perceptual_hash")
                    if isinstance(image.get("perceptual_hash"), str)
                    else None
                ),
                role=ImageRole.PRODUCT,
                duplicate_family_id=str(digest) if digest else sha256_hex(remote.encode("utf-8")),
                fact_class=FactClass.REPORTED_BY_SOURCE,
            )
        )
    fields: dict[str, NormalizedField] = {}
    if title is not None:
        fields["title"] = seller_reported(
            str(title), str(title), method, confidence=0.7, region=region
        )
    if description is not None:
        fields["description"] = seller_reported(
            str(description), str(description), method, confidence=0.6, region=region
        )
    if brand is not None:
        fields["brand"] = seller_reported(
            str(brand), str(brand), method, confidence=0.6, region=region
        )
    if model is not None:
        fields["model"] = seller_reported(
            str(model), str(model), method, confidence=0.5, region=region
        )
    if parsed_price.original:
        fields["price"] = extracted(
            str(parsed_price.amount) if parsed_price.amount is not None else parsed_price.original,
            parsed_price.original,
            method,
            confidence=0.8 if parsed_price.amount is not None else 0.4,
            region=region,
        )
    if parsed_price.currency:
        fields["currency"] = extracted(
            parsed_price.currency,
            parsed_price.currency,
            method,
            confidence=0.9,
            region=region,
        )
    if size_raw is not None:
        fields["size"] = extracted(
            parsed_size.marked,
            parsed_size.original,
            method,
            confidence=0.7 if parsed_size.system else 0.4,
            region=region,
            notes=parsed_size.assumptions,
        )
    fields["availability"] = extracted(
        availability.value,
        str(avail_raw) if avail_raw is not None else None,
        method,
        confidence=0.6 if availability is not Availability.UNKNOWN else 0.2,
        region=region,
    )
    return ListingCandidate(
        candidate_id=candidate_id,
        canonical_url=canon,
        source_adapter=raw.source_adapter,
        source_listing_id=str(payload.get("listing_id") or extract_listing_id(canon) or ""),
        title=_fact(title, seller=True),
        description=_fact(description, seller=True),
        seller_reported_brand=_fact(brand, seller=True),
        seller_reported_model=_fact(model, seller=True),
        price_original=(
            parsed_price.amount if parsed_price.amount is not None else _as_decimal(price_raw)
        ),
        currency_original=parsed_price.currency,
        size_original=parsed_size.original or None,
        condition_reported=_fact(payload.get("condition"), seller=True),
        availability=availability,
        seller_metadata=_seller_meta(payload.get("seller")),
        images=images,
        structured_data={"raw": dict(payload), "originals": _originals(payload)},
        field_records=fields,
        first_seen_at=now,
        last_checked_at=now,
        source_evidence=[raw.content_digest],
        explanation=PublicExplanation(
            live_status=availability,
            last_checked_at=now,
            seller_reported_fields=["title", "brand", "model", "condition"],
        ),
        language=str(payload.get("language")) if payload.get("language") else None,
    )


def _seller_meta(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _originals(payload: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in (
        "title",
        "description",
        "brand",
        "model",
        "price_original",
        "currency",
        "size",
        "availability",
    ):
        value = payload.get(key)
        if value is not None:
            out[key] = str(value)
    return out


def _as_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def originals_preserved(candidate: ListingCandidate) -> bool:
    stored = candidate.structured_data.get("originals")
    if not isinstance(stored, dict):
        return True
    for key, field in candidate.field_records.items():
        original = stored.get(key) if key != "price" else stored.get("price_original")
        if original is None:
            continue
        if field.original is None:
            return False
    return True
