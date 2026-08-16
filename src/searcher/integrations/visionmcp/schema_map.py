"""Map donor dicts onto Searcher types. Donor classes never leave this module."""

from __future__ import annotations

from typing import Any

from searcher.contracts.enums import FactClass, FactOrigin
from searcher.contracts.models import TextObservation
from searcher.core.capabilities import (
    CapabilityName,
    CapabilityRecord,
    CapabilityStability,
)

# Donor capability ids observed at the pinned SHA → Searcher §5.13 names.
DONOR_TO_SEARCHER: dict[str, CapabilityName] = {
    "core.observe_image_file": CapabilityName.IMAGE_DECODE,
    "core.verify_receipts": CapabilityName.RECEIPT_VERIFY,
    "web.chromium_capture": CapabilityName.BROWSER_CAPTURE,
    "ocular.perception": CapabilityName.OBJECT_SEGMENTATION,
}

# Authority ceilings Searcher will claim for a mapped donor row.
DONOR_AUTHORITY: dict[str, str] = {
    "core.observe_image_file": "OBSERVED-pixels",
    "core.verify_receipts": "VERIFIED_DIGEST",
    "web.chromium_capture": "OBSERVED-browser",
    "ocular.perception": "DERIVED-experimental",
}


def _stability(status: str, experimental: bool) -> CapabilityStability:
    if experimental or status in {"experimental", "declared"}:
        return CapabilityStability.EXPERIMENTAL
    if status in {"blocked", "missing", "broken"}:
        return CapabilityStability.UNAVAILABLE
    if status in {"available", "degraded"}:
        return CapabilityStability.STABLE
    return CapabilityStability.UNAVAILABLE


def map_donor_capability_row(row: dict[str, Any]) -> CapabilityRecord | None:
    donor_id = str(row.get("id") or "")
    name = DONOR_TO_SEARCHER.get(donor_id)
    if name is None:
        return None
    status = str(row.get("status") or "unknown")
    experimental = bool(row.get("experimental"))
    available = status in {"available", "degraded"} and not experimental
    if name is CapabilityName.OBJECT_SEGMENTATION:
        # Ocular segment is deferred. Never report it as a product segmenter.
        available = False
    return CapabilityRecord(
        name=name,
        available=available,
        stability=_stability(status, experimental),
        dependency=str(row.get("plugin") or row.get("adapter") or "visionmcp"),
        resource_cost=str(row.get("resource_cost") or "unknown"),
        authority_ceiling=DONOR_AUTHORITY.get(donor_id, "DECLARED"),
        notes=str(row.get("summary") or row.get("detail") or donor_id),
    )


def map_inspect_image(metadata: dict[str, Any], quality: dict[str, Any]) -> dict[str, Any]:
    """Strip donor-only keys into a Searcher calibration dict."""
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    return {
        "width": width,
        "height": height,
        "source_width": int(metadata.get("source_width") or width),
        "source_height": int(metadata.get("source_height") or height),
        "format": str(metadata.get("format") or "unknown"),
        "mode": str(metadata.get("mode") or "unknown"),
        "orientation": str(metadata.get("orientation") or "unknown"),
        "orientation_corrected": bool(metadata.get("orientation_corrected")),
        "colour_space": str(metadata.get("mode") or "unknown"),
        "decode_ok": bool(quality.get("decode_ok")),
        "exposure_mean": float(quality.get("exposure_mean") or 0.0),
        "edge_variance": float(quality.get("edge_variance") or 0.0),
        "blur_warning": bool(quality.get("blur_warning")),
        "exposure_warning": bool(quality.get("exposure_warning")),
        "clipped_black_fraction": float(quality.get("clipped_black_fraction") or 0.0),
        "clipped_white_fraction": float(quality.get("clipped_white_fraction") or 0.0),
        "has_icc": bool((metadata.get("color_profile") or {}).get("embedded")),
        # EXIF camera/lens stay in quarantine; never promoted to identity.
        "has_exif": bool(metadata.get("exif")),
    }


def map_ocr_symbols(symbols: list[dict[str, Any]]) -> list[TextObservation]:
    observations: list[TextObservation] = []
    for symbol in symbols:
        text = str(symbol.get("text") or "").strip()
        if not text:
            continue
        bounds = symbol.get("bounds") or {}
        region = (
            float(bounds.get("x") or 0.0),
            float(bounds.get("y") or 0.0),
            float(bounds.get("width") or 0.0),
            float(bounds.get("height") or 0.0),
        )
        try:
            confidence = float(symbol.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        observations.append(
            TextObservation(
                text=text,
                region=region,
                confidence=max(0.0, min(1.0, confidence)),
                fact_class=FactClass.EXTRACTED,
                origin=FactOrigin.EXTRACTOR,
                kind="unknown",
            )
        )
    return observations


def map_regions(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for region in regions:
        bounds = region.get("bounds") or {}
        mapped.append(
            {
                "region": (
                    float(bounds.get("x") or 0.0),
                    float(bounds.get("y") or 0.0),
                    float(bounds.get("width") or 0.0),
                    float(bounds.get("height") or 0.0),
                ),
                "confidence": float(region.get("confidence") or 0.0),
                "mean_rgb": list(region.get("mean_rgb") or []),
                "authority": "DERIVED",
            }
        )
    return mapped
