"""§18.3 subject isolation. Never compare a whole screenshot to a whole page."""

from __future__ import annotations

from searcher.contracts.enums import ImageRole
from searcher.contracts.models import ListingImage
from searcher.matching.types import IsolatedSubject
from searcher.reference.imaging import decode_and_normalize, subject_bbox


def isolate_subjects(
    images: list[tuple[ListingImage, bytes]],
) -> list[IsolatedSubject]:
    isolated: list[IsolatedSubject] = []
    for image, raw in images:
        decoded = decode_and_normalize(raw)
        png = decoded.rgb_png
        bbox = subject_bbox(png)
        _x, _y, w, h = bbox
        area = (w * h) / max(1, decoded.width * decoded.height)
        role = image.role.value if image.role else ImageRole.UNKNOWN.value
        relevant = True
        reason = "subject"
        if area < 0.04:
            relevant = False
            reason = "subject_too_small_probably_icon"
        elif area > 0.98 and min(decoded.width, decoded.height) > 800:
            # Full-frame page screenshot with no isolated product.
            relevant = role in {
                ImageRole.PRODUCT.value,
                ImageRole.LABEL.value,
                ImageRole.SOLE.value,
            }
            reason = "full_frame"
        if role == ImageRole.SCREENSHOT.value and area < 0.2:
            relevant = False
            reason = "screenshot_without_product"
        isolated.append(
            IsolatedSubject(
                image_id=image.listing_image_id,
                png=png,
                bbox=bbox,
                subject_area=round(area, 4),
                relevant=relevant,
                role=role,
                reason=reason,
                width=decoded.width,
                height=decoded.height,
            )
        )
    return isolated


def gallery_images(subjects: list[IsolatedSubject]) -> list[IsolatedSubject]:
    return [item for item in subjects if item.relevant]
