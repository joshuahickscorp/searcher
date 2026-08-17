"""Two photographs of one label are not evidence of a counterfeit.

`label_hash` is a perceptual hash of a label region, not a product code. Any two
honest photographs of the same label — different angle, exposure, JPEG quality —
hash differently. Treating that inequality as a hard contradiction produced
STRONG_COUNTERFEIT_EVIDENCE against a real listing, and produced it
inconsistently: it fired only when both sides happened to yield a hash, which
depended on which images the shop served that minute.
"""

from __future__ import annotations

from searcher.authenticity.labels import assess_labels
from searcher.matching.types import StructuredDescriptor


def _with_label(label: str | None) -> StructuredDescriptor:
    return StructuredDescriptor(
        image_id="x",
        width=512,
        height=512,
        aspect=1.0,
        subject_area=0.6,
        centroid=(0.5, 0.5),
        eyelet_count=0,
        panel_count=2,
        seam_count=2,
        outsole_ratio=0.0,
        sole_to_upper=0.0,
        heel_aspect=0.0,
        heel_cut="none",
        heel_angle=0.0,
        logo_xy=None,
        logo_kind=None,
        tread_kind="none",
        label_hash=label,
        dominant_rgb=(20.0, 20.0, 20.0),
        smoothness=0.2,
        keypoints=120,
    )


def test_differing_label_hashes_are_unresolved_not_counterfeit() -> None:
    score, hard, missing = assess_labels(
        reference=_with_label("aaaa1111"),
        candidate=_with_label("bbbb2222"),
        listing_text=None,
        reference_code=None,
    )
    assert hard == []
    assert "label-code-unresolved" in missing
    assert 0.3 < score.interval.mean < 0.6


def test_matching_label_hashes_still_corroborate() -> None:
    score, hard, _missing = assess_labels(
        reference=_with_label("aaaa1111"),
        candidate=_with_label("aaaa1111"),
        listing_text=None,
        reference_code=None,
    )
    assert hard == []
    assert score.interval.mean >= 0.8


def test_a_missing_label_view_is_still_missing() -> None:
    _score, hard, missing = assess_labels(
        reference=_with_label("aaaa1111"),
        candidate=_with_label(None),
        listing_text=None,
        reference_code=None,
    )
    assert hard == []
    assert "label-view" in missing
