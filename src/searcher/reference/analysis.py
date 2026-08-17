"""Build the §11.9 ReferenceAnalysis from stored, already-validated images."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from searcher.contracts.enums import FactClass, ViewHypothesis
from searcher.contracts.models import (
    CategoryHypothesis,
    ImageQuality,
    LaneStatus,
    ReferenceAnalysis,
    ReferenceCrop,
    ReferenceDerived,
    ReferenceImage,
    TextObservation,
    Uncertainty,
)
from searcher.contracts.primitives import ArtifactRef
from searcher.core.capabilities import CapabilityName
from searcher.core.config import Settings
from searcher.core.errors import InputError
from searcher.core.ids import new_id
from searcher.evidence.content_store import ContentStore
from searcher.integrations.visionmcp.probe import probe_capabilities
from searcher.reference.gaps import evidence_gaps
from searcher.reference.imaging import (
    average_hash,
    colour_histogram,
    crop_png,
    decode_and_normalize,
    subject_bbox,
)
from searcher.reference.ocr import run_tesseract
from searcher.reference.parts import parts_for_view
from searcher.reference.quality import score_quality
from searcher.reference.signature import build_signature
from searcher.reference.unify import unify_references
from searcher.reference.validation import validate_upload_bytes
from searcher.reference.views import classify_view
from searcher.reference.vocab import CATEGORIES


def _lane_status(report_notes: dict[CapabilityName, Any]) -> list[LaneStatus]:
    probe = probe_capabilities()
    lanes: list[LaneStatus] = []
    for record in probe.capabilities:
        lanes.append(
            LaneStatus(
                name=record.name.value,
                available=record.available,
                blocked=not record.available,
                degraded=record.name
                in {
                    CapabilityName.DENSE_FEATURES,
                    CapabilityName.OBJECT_SEGMENTATION,
                    CapabilityName.LOCAL_CORRESPONDENCE,
                    CapabilityName.MATERIAL_ANALYSIS,
                    CapabilityName.LOGO_DETECTION,
                }
                and not record.available,
                reason=record.notes,
                authority_ceiling=record.authority_ceiling,
            )
        )
    del report_notes
    return lanes


def _promotion_blocked(lanes: list[LaneStatus]) -> bool:
    critical = {
        CapabilityName.DENSE_FEATURES.value,
        CapabilityName.OBJECT_SEGMENTATION.value,
        CapabilityName.LOCAL_CORRESPONDENCE.value,
    }
    return any(lane.name in critical and (lane.blocked or lane.degraded) for lane in lanes)


def _category_from_signals(
    ocr: list[TextObservation], text: str | None, tags: list[str]
) -> list[CategoryHypothesis]:
    tokens = [*(text or "").split(), *tags, *(item.text for item in ocr)]
    found: dict[str, float] = {}
    for token in tokens:
        mapped = CATEGORIES.get(token.lower())
        if mapped:
            found[mapped] = max(found.get(mapped, 0.0), 0.55)
    if not found:
        found["unknown"] = 0.2
    return [
        CategoryHypothesis(
            category=name,
            confidence=conf,
            fact_class=FactClass.INFERRED,
            evidence=["user_or_ocr_token"],
        )
        for name, conf in found.items()
    ]


def analyze_stored_references(
    store: ContentStore,
    images: list[ArtifactRef],
    *,
    text: str | None,
    tags: list[str],
    search_id: str,
    settings: Settings | None = None,
    donor_inspect: Callable[[Path], dict[str, Any] | None] | None = None,
) -> ReferenceAnalysis:
    cfg = settings or Settings.from_env()
    # The view vocabulary depends on what the thing is. Derived from the user's
    # own words here, before any crop is classified, because a garment's front
    # must not be named a shoe's top.
    hint_source = f"{text or ''} {' '.join(tags or [])}".lower()
    category_hint = "footwear" if any(
        word in hint_source
        for word in ("shoe", "sneaker", "trainer", "boot", "pump", "loafer", "heel", "sandal")
    ) else "garment"
    if len(images) > cfg.max_images_per_search:
        raise InputError(f"too many images (max {cfg.max_images_per_search})")
    if not images:
        raise InputError("at least one image is required")

    lanes = _lane_status({})
    blocked = _promotion_blocked(lanes)
    donor_invoked = False
    donor_version: str | None = None

    records: list[ReferenceImage] = []
    pngs: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    histograms: dict[str, list[float]] = {}
    quality_map: dict[str, ImageQuality] = {}
    all_ocr: list[TextObservation] = []
    view_entries = []
    part_entries = []
    collage_flags: dict[str, bool] = {}
    worn_flags: dict[str, bool] = {}
    screenshot_flags: dict[str, bool] = {}

    tmp_root = store.zones["temporary"] / search_id
    tmp_root.mkdir(parents=True, exist_ok=True)

    for index, ref in enumerate(images):
        raw = store.get(ref.digest, campaign_id=search_id)
        validated = validate_upload_bytes(raw, settings=cfg)
        decoded = decode_and_normalize(raw, settings=cfg)
        image_id = f"ref-{index:02d}-{ref.digest[:12]}"
        norm_digest = store.put_bytes(
            decoded.rgb_png, zone="derived", campaign_id=search_id, private=True
        )
        thumb_digest = store.put_bytes(
            decoded.thumbnail_png, zone="derived", campaign_id=search_id, private=True
        )
        if decoded.exif_quarantine:
            import json

            store.put_bytes(
                json.dumps(decoded.exif_quarantine, sort_keys=True).encode("utf-8"),
                zone="quarantine",
                campaign_id=search_id,
                private=True,
            )

        donor_meta: dict[str, Any] | None = None
        if donor_inspect is not None:
            tmp_path = tmp_root / f"{ref.digest}.img"
            tmp_path.write_bytes(raw)
            try:
                donor_meta = donor_inspect(tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)
            if donor_meta is not None:
                donor_invoked = True

        ocr_tmp = tmp_root / f"{ref.digest}.png"
        ocr_tmp.write_bytes(decoded.rgb_png)
        try:
            ocr = run_tesseract(ocr_tmp)
        finally:
            ocr_tmp.unlink(missing_ok=True)
        all_ocr.extend(ocr)
        text_vis = max((item.confidence for item in ocr), default=0.0)

        x, y, w, h = subject_bbox(decoded.rgb_png)
        crop_bytes = crop_png(decoded.rgb_png, (x, y, w, h))
        crop_digest = store.put_bytes(
            crop_bytes, zone="derived", campaign_id=search_id, private=True
        )
        crop = ReferenceCrop(
            crop_id=new_id(),
            parent_image_id=image_id,
            region=(float(x), float(y), float(w), float(h)),
            object_hypothesis="salient_subject",
            part_hypothesis=None,
            view_hypothesis=ViewHypothesis.UNKNOWN,
            confidence=0.45,
            mask_ref=None,
            feature_ref=crop_digest,
            fact_class=FactClass.INFERRED,
        )
        view = classify_view(
            crop_id=crop.crop_id,
            width=w,
            height=h,
            region=crop.region,
            parent_width=decoded.width,
            parent_height=decoded.height,
            ocr=ocr,
            subject_area=(w * h) / max(1, decoded.width * decoded.height),
            category=category_hint,
        )
        crop = crop.model_copy(update={"view_hypothesis": view.view, "confidence": view.confidence})
        view_entries.append(view)
        part_entries.extend(parts_for_view(view))

        quality = score_quality(
            decoded.rgb_png,
            width=decoded.width,
            height=decoded.height,
            media_type=validated.media_type,
            text_visibility=text_vis,
            unique_angle=False,
            donor_blur_warning=(donor_meta or {}).get("blur_warning"),
            donor_exposure_warning=(donor_meta or {}).get("exposure_warning"),
        )
        quality_map[image_id] = quality
        pngs[image_id] = decoded.rgb_png
        hashes[image_id] = average_hash(decoded.rgb_png)
        histograms[image_id] = colour_histogram(decoded.rgb_png)

        ocr_kinds = {item.kind for item in ocr}
        screenshot_flags[image_id] = "overlay" in ocr_kinds or "handle" in ocr_kinds
        worn_flags[image_id] = view.view is ViewHypothesis.WORN
        collage_flags[image_id] = (w * h) / max(1, decoded.width * decoded.height) < 0.25 and len(
            ocr
        ) > 8

        records.append(
            ReferenceImage(
                reference_image_id=image_id,
                content_digest=ref.digest,
                media_type=validated.media_type,
                byte_length=validated.byte_length,
                width=decoded.width,
                height=decoded.height,
                orientation=decoded.orientation,
                colour_space=decoded.colour_space,
                source="user_upload",
                privacy_state="private",
                derived=ReferenceDerived(
                    normalized_image=norm_digest,
                    thumbnail=thumb_digest,
                    masks=[],
                    crops=[crop],
                    ocr=ocr,
                    feature_sets=[crop_digest],
                ),
                quality=quality,
                fact_class=FactClass.USER_SUPPLIED,
            )
        )

    # Unique-angle bonus: a view that appears once keeps its image even if low quality.
    view_counts: dict[str, int] = {}
    for rec in records:
        for crop in rec.derived.crops:
            key = crop.view_hypothesis.value
            view_counts[key] = view_counts.get(key, 0) + 1
    for rec in records:
        unique = any(view_counts.get(c.view_hypothesis.value, 0) == 1 for c in rec.derived.crops)
        if unique:
            quality_map[rec.reference_image_id] = score_quality(
                pngs[rec.reference_image_id],
                width=rec.width,
                height=rec.height,
                media_type=rec.media_type,
                text_visibility=rec.quality.text_visibility,
                unique_angle=True,
            )
            rec.quality = quality_map[rec.reference_image_id]

    primary, alternates = unify_references(
        [rec.reference_image_id for rec in records],
        hashes,
        histograms,
        collage_flags=collage_flags,
        worn_flags=worn_flags,
        screenshot_flags=screenshot_flags,
    )
    crop_ids = [crop.crop_id for rec in records for crop in rec.derived.crops]
    primary = primary.model_copy(update={"crop_ids": crop_ids})

    dense_ok = any(
        lane.name == CapabilityName.DENSE_FEATURES.value and lane.available for lane in lanes
    )
    signature = build_signature(
        image_pngs=pngs,
        ocr=all_ocr,
        parts=part_entries,
        dense_features_available=dense_ok,
    )
    analysis = ReferenceAnalysis(
        analysis_id=new_id(),
        search_id=search_id,
        images=records,
        primary_cluster=primary,
        alternate_clusters=alternates,
        quality_map=quality_map,
        view_inventory=view_entries,
        part_inventory=part_entries,
        text_and_marks=all_ocr,
        visual_signature=signature,
        category_hypotheses=_category_from_signals(all_ocr, text, tags),
        evidence_gaps=[],
        lanes=lanes,
        promotion_blocked=blocked,
        donor_invoked=donor_invoked,
        donor_version=donor_version,
        uncertainties=[
            Uncertainty(
                question="learned identity embedding unavailable",
                impact="cannot promote a visual-only match to a public result",
                missing_evidence=["dense_features"],
            )
        ]
        if blocked
        else [],
    )
    analysis = analysis.model_copy(update={"evidence_gaps": evidence_gaps(analysis)})
    return analysis
