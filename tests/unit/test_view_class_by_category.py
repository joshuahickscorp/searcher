"""Footwear views must not be applied to things that are not footwear.

A long-sleeve shirt was classified "heel" because the product-role branch read
aspect ratio with footwear hypotheses regardless of category. Its views could
then never match the views its own profile expects, so evidence completeness
stayed at its floor and no garment could reach Real however well it matched.
"""

from __future__ import annotations

from searcher.contracts.enums import ImageRole, ViewHypothesis
from searcher.matching.types import IsolatedSubject
from searcher.matching.views import classify_listing_view


def _subject(area: float, width: int = 1024, height: int = 1024) -> IsolatedSubject:
    return IsolatedSubject(
        image_id="i1",
        png=b"",
        bbox=(0, 0, width, height),
        subject_area=area,
        relevant=True,
        role=ImageRole.PRODUCT.value,
        width=width,
        height=height,
    )


def test_a_garment_filling_the_frame_is_a_front_view() -> None:
    guess = classify_listing_view(_subject(0.64), category="garment")
    assert guess.view is ViewHypothesis.FRONT


def test_a_close_crop_of_a_garment_is_a_detail_view() -> None:
    guess = classify_listing_view(_subject(0.12), category="garment")
    assert guess.view is ViewHypothesis.DETAIL


def test_footwear_keeps_its_own_reading() -> None:
    guess = classify_listing_view(_subject(0.64), category="footwear")
    assert guess.view in {ViewHypothesis.HEEL, ViewHypothesis.LATERAL}


def test_an_unknown_category_is_not_treated_as_footwear() -> None:
    guess = classify_listing_view(_subject(0.64), category=None)
    assert guess.view is ViewHypothesis.FRONT
