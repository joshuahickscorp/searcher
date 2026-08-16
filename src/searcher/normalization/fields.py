"""Build §16.5 NormalizedField values. Seller claims stay REPORTED_BY_SELLER."""

from __future__ import annotations

from searcher.contracts.enums import ExtractionMethod, FactClass, FactOrigin
from searcher.contracts.primitives import NormalizedField


def extracted(
    value: str | int | float | bool | None,
    original: str | None,
    method: ExtractionMethod,
    *,
    confidence: float,
    region: str | None = None,
    notes: str | None = None,
) -> NormalizedField:
    return NormalizedField(
        value=value,
        original=original,
        extraction_method=method,
        source_region=region,
        confidence=confidence,
        fact_class=FactClass.EXTRACTED,
        origin=FactOrigin.EXTRACTOR,
        conversion_notes=notes,
    )


def seller_reported(
    value: str | int | float | bool | None,
    original: str | None,
    method: ExtractionMethod,
    *,
    confidence: float,
    region: str | None = None,
) -> NormalizedField:
    return NormalizedField(
        value=value,
        original=original,
        extraction_method=method,
        source_region=region,
        confidence=confidence,
        fact_class=FactClass.REPORTED_BY_SELLER,
        origin=FactOrigin.SELLER,
    )


def source_reported(
    value: str | int | float | bool | None,
    original: str | None,
    method: ExtractionMethod,
    *,
    confidence: float,
    region: str | None = None,
) -> NormalizedField:
    return NormalizedField(
        value=value,
        original=original,
        extraction_method=method,
        source_region=region,
        confidence=confidence,
        fact_class=FactClass.REPORTED_BY_SOURCE,
        origin=FactOrigin.SOURCE,
    )
