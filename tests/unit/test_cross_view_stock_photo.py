"""The stock-photo contradiction must not fire on ordinary resale galleries.

A seller who lays a garment flat and then crops in on a seam produces images
whose smoothness differs by design. Before this rule was scoped to a view class,
that gap alone capped the score at 0.4 and suppressed the true listing.
"""

from __future__ import annotations

from searcher.matching.cross_image import cross_view_consistency
from searcher.matching.types import StructuredDescriptor


def _descriptor(image_id: str, *, smoothness: float, subject_area: float) -> StructuredDescriptor:
    return StructuredDescriptor(
        image_id=image_id,
        width=1024,
        height=1024,
        aspect=1.0,
        subject_area=subject_area,
        centroid=(0.5, 0.5),
        eyelet_count=0,
        panel_count=0,
        seam_count=2,
        outsole_ratio=0.0,
        sole_to_upper=0.0,
        heel_aspect=0.0,
        heel_cut="none",
        heel_angle=0.0,
        logo_xy=None,
        logo_kind=None,
        tread_kind="none",
        label_hash=None,
        dominant_rgb=(20.0, 20.0, 20.0),
        smoothness=smoothness,
        keypoints=120,
    )


def test_full_shot_beside_a_detail_crop_is_not_a_stock_photo_gap() -> None:
    # A flat-lay of the whole garment, then a close crop of the fabric.
    descriptors = [
        _descriptor("full", smoothness=0.90, subject_area=0.72),
        _descriptor("detail", smoothness=0.20, subject_area=0.18),
    ]
    _score, contradictions, _missing = cross_view_consistency(
        descriptors, apply_footwear_rules=False
    )
    assert "stock-photo-smoothness-gap" not in contradictions


def test_two_full_shots_that_disagree_are_still_flagged() -> None:
    # Same view class: one pristine stock render, one rough snapshot.
    descriptors = [
        _descriptor("stock", smoothness=0.95, subject_area=0.70),
        _descriptor("snapshot", smoothness=0.18, subject_area=0.68),
    ]
    _score, contradictions, _missing = cross_view_consistency(
        descriptors, apply_footwear_rules=False
    )
    assert "stock-photo-smoothness-gap" in contradictions


def test_size_charts_and_banners_are_not_judged_as_photographs() -> None:
    """Real resale listings carry diagrams. They are not photographs of the item.

    Measured on the live KIND listing 8001001141404: its gallery holds two
    photographs of the garment (smoothness 0.000 each) and three shop graphics
    with no segmentable subject (0.000, 0.716, 0.336). Judging those together
    produced a 0.716 spread and suppressed the true listing.
    """
    photographs = [
        _descriptor("lateral-a", smoothness=0.0, subject_area=0.635),
        _descriptor("lateral-b", smoothness=0.0, subject_area=0.565),
    ]
    graphics = [
        _descriptor("size-chart", smoothness=0.0, subject_area=1.0),
        _descriptor("condition-table", smoothness=0.716, subject_area=1.0),
        _descriptor("shop-banner", smoothness=0.336, subject_area=1.0),
    ]
    _score, contradictions, _missing = cross_view_consistency(
        photographs + graphics, apply_footwear_rules=False
    )
    assert "stock-photo-smoothness-gap" not in contradictions
