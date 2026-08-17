"""Adding reference views must not lower item-match for the same candidate."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image, ImageDraw
from tests.helpers_matching import make_candidate, make_hypothesis

from searcher.contracts.enums import ImageRole
from searcher.matching.broad import global_visual as real_global_visual
from searcher.matching.pipeline import enrich_candidate, match_candidate, prepare_reference


def _bag_png(kind: str) -> bytes:
    """Same brown bag, different compositions.

    Insertion order is front-first. A fill-frame detail has the largest
    subject_area, so the old primary-descriptor pick is not the first png.
    """
    leather = (92, 58, 42)
    hardware = (210, 180, 90)
    outline = (30, 18, 12)
    bg = (236, 232, 224)
    if kind == "front":
        image = Image.new("RGB", (200, 260), bg)
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 70, 160, 230), fill=leather, outline=outline, width=3)
        draw.arc((60, 40, 140, 110), 0, 180, fill=outline, width=6)
        draw.rectangle((85, 100, 115, 130), fill=hardware)
    elif kind == "side":
        image = Image.new("RGB", (320, 280), bg)
        draw = ImageDraw.Draw(image)
        draw.polygon([(70, 80), (250, 60), (270, 230), (50, 240)], fill=leather, outline=outline)
        draw.rectangle((140, 90, 180, 140), fill=hardware)
    elif kind == "top":
        image = Image.new("RGB", (280, 220), bg)
        draw = ImageDraw.Draw(image)
        draw.ellipse((40, 40, 240, 180), fill=leather, outline=outline, width=3)
        draw.ellipse((90, 80, 190, 140), fill=(70, 44, 32))
    elif kind == "detail":
        image = Image.new("RGB", (360, 360), bg)
        draw = ImageDraw.Draw(image)
        draw.rectangle((12, 12, 348, 348), fill=leather)
        draw.rectangle((120, 120, 240, 220), fill=hardware)
        draw.ellipse((150, 145, 210, 195), fill=(40, 24, 16))
    else:
        image = Image.new("RGB", (210, 270), bg)
        draw = ImageDraw.Draw(image)
        draw.rectangle((35, 65, 175, 240), fill=(80, 50, 36), outline=outline, width=3)
        draw.rectangle((70, 90, 140, 160), fill=(60, 38, 28))
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


_VIEW_ORDER = ("front", "side", "top", "detail", "back")


def _bag_views() -> dict[str, bytes]:
    return {name: _bag_png(name) for name in _VIEW_ORDER}


def _score(*, hypothesis, candidate, reference_pngs):
    return match_candidate(
        hypothesis=hypothesis,
        candidate=candidate,
        reference_pngs=reference_pngs,
        reference_descriptors=prepare_reference(reference_pngs),
    )


def test_adding_reference_views_does_not_lower_item_match() -> None:
    views = _bag_views()
    listing, cand_pngs = make_candidate(
        images=[("storefront", views["front"], ImageRole.PRODUCT)],
        title="brown leather tote",
    )
    hyp = make_hypothesis(category="bag")
    enriched = enrich_candidate(listing, cand_pngs, category="bag")

    one = {"front": views["front"]}
    first = _score(hypothesis=hyp, candidate=enriched, reference_pngs=one)
    fifth = _score(hypothesis=hyp, candidate=enriched, reference_pngs=views)

    one_mean = first.item_match_distribution.mean
    five_mean = fifth.item_match_distribution.mean
    assert five_mean >= one_mean, f"1-view mean={one_mean} 5-view mean={five_mean}"


def test_global_visual_gets_descriptor_and_pixels_from_the_same_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    views = _bag_views()
    listing, cand_pngs = make_candidate(
        images=[(name, views[name], ImageRole.PRODUCT) for name in _VIEW_ORDER],
        title="brown leather tote",
    )
    hyp = make_hypothesis(category="bag")
    enriched = enrich_candidate(listing, cand_pngs, category="bag")
    seen: list[tuple[str, bytes, str, bytes]] = []

    def _capture(ref_desc, cand_desc, *, reference_png, candidate_png):
        seen.append((ref_desc.image_id, reference_png, cand_desc.image_id, candidate_png))
        return real_global_visual(
            ref_desc, cand_desc, reference_png=reference_png, candidate_png=candidate_png
        )

    monkeypatch.setattr("searcher.matching.pipeline.global_visual", _capture)
    _score(hypothesis=hyp, candidate=enriched, reference_pngs=views)

    assert seen
    for ref_id, ref_png, cand_id, cand_png in seen:
        if ref_png != views[ref_id]:
            raise AssertionError(
                f"global_visual got descriptor {ref_id!r} but pixels from another image "
                f"(expected {len(views[ref_id])} bytes, got {len(ref_png)} bytes)"
            )
        if cand_png != cand_pngs[cand_id]:
            raise AssertionError(
                f"global_visual got candidate descriptor {cand_id!r} but pixels "
                f"from another image"
            )
