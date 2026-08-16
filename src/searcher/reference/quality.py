"""§11.5 quality assessment. Quality allocates weight; unique angles are kept."""

from __future__ import annotations

from searcher.contracts.models import ImageQuality
from searcher.reference.imaging import edge_stats, exposure_mean, subject_bbox


def score_quality(
    png_bytes: bytes,
    *,
    width: int,
    height: int,
    media_type: str,
    text_visibility: float = 0.0,
    unique_angle: bool = False,
    donor_blur_warning: bool | None = None,
    donor_exposure_warning: bool | None = None,
) -> ImageQuality:
    edge_var, edge_mean = edge_stats(png_bytes)
    blur = 0.2 if donor_blur_warning else min(1.0, edge_var / 400.0)
    if donor_blur_warning is False:
        blur = max(blur, 0.55)
    mean = exposure_mean(png_bytes)
    lighting = 1.0 - min(1.0, abs(mean - 0.5) * 2.0)
    if donor_exposure_warning:
        lighting = min(lighting, 0.35)
    resolution = min(1.0, min(width, height) / 800.0)
    compression = 0.55 if media_type == "image/jpeg" else 0.8
    if media_type == "image/jpeg" and edge_mean < 0.04:
        compression = 0.35
    x, y, w, h = subject_bbox(png_bytes)
    area = max(1, width * height)
    subject_area = min(1.0, (w * h) / area)
    border = 0.12
    near_border = x < width * border or y < height * border or (x + w) > width * (1 - border)
    occlusion = 0.35 if near_border and subject_area < 0.4 else 0.15
    if subject_area < 0.15:
        occlusion = 0.55
    aspect = width / max(1, height)
    perspective = 0.7 if 0.6 <= aspect <= 1.8 else 0.45
    background = min(1.0, 0.3 + subject_area)
    part_visibility = min(1.0, 0.3 + subject_area * 0.5 + (0.2 if unique_angle else 0.0))
    usable: list[str] = []
    if resolution >= 0.35 and blur >= 0.35:
        usable.append("global_identity")
    if part_visibility >= 0.4:
        usable.append("side_panel")
    if unique_angle:
        usable.append("unique_angle")
    weight = (
        0.20 * resolution
        + 0.15 * blur
        + 0.10 * compression
        + 0.10 * (1.0 - occlusion)
        + 0.10 * lighting
        + 0.15 * subject_area
        + 0.10 * background
        + 0.05 * text_visibility
        + 0.05 * part_visibility
    )
    if unique_angle:
        weight = min(1.0, weight + 0.12)
    return ImageQuality(
        blur=round(blur, 4),
        compression=round(compression, 4),
        occlusion=round(occlusion, 4),
        subject_area=round(subject_area, 4),
        resolution=round(resolution, 4),
        perspective=round(perspective, 4),
        lighting=round(lighting, 4),
        background_interference=round(1.0 - background, 4),
        text_visibility=round(text_visibility, 4),
        part_visibility=round(part_visibility, 4),
        weight=round(min(1.0, max(0.05, weight)), 4),
        usable_for=usable,
    )
