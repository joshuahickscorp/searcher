"""Real-gate inputs: every term that feeds item_match and authenticity.

The public gate still requires item_match_lower_bound >= 0.90 and
authenticity_lower_bound >= 0.80. This file does not move those numbers.
It checks that the combination consumes the evidence that already exists
(correspondence inliers, category parts, garment views) and records which
authenticity terms stay short on honest measurements.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageEnhance
from tests.helpers_matching import constraints, make_candidate, make_hypothesis, views_for

from searcher.authenticity.completeness import completeness
from searcher.authenticity.decision import AUTH_WEIGHTS
from searcher.authenticity.engine import assess_authenticity
from searcher.authenticity.profiles import profile_for
from searcher.contracts.enums import (
    BucketPublic,
    FactClass,
    FactOrigin,
    ImageRole,
    ViewHypothesis,
)
from searcher.contracts.primitives import classified
from searcher.matching.combine import ITEM_WEIGHTS, combine_item_match
from searcher.matching.correspondence import correspond_pair
from searcher.matching.features import opencv_available
from searcher.matching.ontology import ontology_for
from searcher.matching.pipeline import (
    CORRESPONDENCE_STRONG_INLIERS,
    apply_category,
    enrich_candidate,
    match_candidate,
    prepare_reference,
)
from searcher.matching.scores import scored
from searcher.matching.synth import REFERENCE_SHOE, render_views
from searcher.matching.types import IsolatedSubject, StructuredDescriptor, ViewGuess
from searcher.matching.views import classify_listing_view, refine_views
from searcher.ranking.buckets import route_candidate
from searcher.ranking.policy_versions import load_policy
from searcher.ranking.utility import listing_utility


def _png(*, colour: tuple[int, int, int] = (24, 36, 80), shift: int = 0) -> bytes:
    image = Image.new("RGB", (240, 320), colour)
    draw = ImageDraw.Draw(image)
    draw.rectangle((40 + shift, 50, 200 + shift, 270), fill=(190, 28, 28))
    draw.ellipse((90 + shift, 90, 150 + shift, 160), fill=(240, 210, 40))
    draw.line((60, 200, 180, 250), fill=(12, 12, 12), width=6)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _warped(png: bytes) -> bytes:
    image = Image.open(BytesIO(png)).convert("RGB")
    image = ImageEnhance.Brightness(image).enhance(1.05)
    image = image.transform(
        image.size,
        Image.Transform.PERSPECTIVE,
        (1, 0.04, 4, 0.02, 1, 3, 0.0001, 0.0002),
        resample=Image.Resampling.BILINEAR,
    )
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def _descriptor(
    image_id: str,
    *,
    eyelets: int = 0,
    panels: int = 1,
    label_hash: str | None = None,
    area: float = 0.62,
    aspect: float = 0.75,
) -> StructuredDescriptor:
    return StructuredDescriptor(
        image_id=image_id,
        width=1024,
        height=1024,
        aspect=aspect,
        subject_area=area,
        centroid=(0.5, 0.5),
        eyelet_count=eyelets,
        panel_count=panels,
        seam_count=3,
        outsole_ratio=0.4,
        sole_to_upper=0.5,
        heel_aspect=0.3,
        heel_cut="block",
        heel_angle=0.2,
        logo_xy=None,
        logo_kind=None,
        tread_kind="none",
        label_hash=label_hash,
        dominant_rgb=(18.0, 18.0, 18.0),
        smoothness=0.35,
        keypoints=80,
    )


def _subject(image_id: str = "front", area: float = 0.64) -> IsolatedSubject:
    return IsolatedSubject(
        image_id=image_id,
        png=_png(),
        bbox=(0, 0, 1024, 1024),
        subject_area=area,
        relevant=True,
        role=ImageRole.PRODUCT.value,
        width=1024,
        height=1024,
    )


def test_item_and_auth_weights_were_not_retuned() -> None:
    assert ITEM_WEIGHTS["parts"] == 0.30
    assert ITEM_WEIGHTS["text"] == 0.18
    assert ITEM_WEIGHTS["global"] == 0.18
    assert ITEM_WEIGHTS["geometry"] == 0.16
    assert abs(sum(ITEM_WEIGHTS.values()) - 1.0) < 1e-9
    assert abs(sum(AUTH_WEIGHTS.values()) - 1.0) < 1e-9
    policy = load_policy("matching-1")
    assert policy.real.item_match_lower_bound == 0.90
    assert policy.real.authenticity_lower_bound == 0.80


def test_a_garment_front_is_not_refined_into_a_heel() -> None:
    guess = classify_listing_view(_subject(), category="garment")
    assert guess.view is ViewHypothesis.FRONT
    # Fake eyelets: the structure extractor counts shirt highlights as holes.
    refined = refine_views(
        [guess],
        {"front": _descriptor("front", eyelets=7, panels=5)},
        category="garment",
    )
    assert refined[0].view is ViewHypothesis.FRONT


def test_shirt_aliases_use_the_garment_ontology() -> None:
    for key in ("shirt", "long-sleeve", "cutsew", "clothing"):
        assert ontology_for(key).profile_id == "designer_garment"
        assert "collar" in ontology_for(key).part_names()
        assert "eyelets" not in ontology_for(key).part_names()


def test_correspondence_is_cited_with_its_inlier_count() -> None:
    reference = _png()
    candidate_png = _warped(reference)
    listing, pngs = make_candidate(
        images=[("front", candidate_png, ImageRole.PRODUCT)],
        title="WILLY CHAVARRIA long sleeve",
    )
    hyp = make_hypothesis(category="garment")
    enriched = enrich_candidate(listing, pngs, category="garment")
    apply_category(enriched, "garment")
    match = match_candidate(
        hypothesis=hyp,
        candidate=enriched,
        reference_pngs={"user": reference},
        reference_descriptors=prepare_reference({"user": reference}),
    )
    measured = correspond_pair(reference, candidate_png)
    cites = [item for item in match.explanation.support if item.startswith("ev:correspondence:")]
    assert cites, match.explanation.support
    assert any("-inliers" in item for item in cites)
    assert any(f"{measured.method}:" in item for item in cites)
    assert any("-inliers" in item for item in match.geometry.support)
    part_names = {item.part_name for item in match.part_correspondence}
    assert "eyelets" not in part_names
    assert "outsole" not in part_names
    assert "heel" not in part_names


@pytest.mark.skipif(not opencv_available(), reason="opencv is the correspondence extra")
def test_strong_correspondence_sets_geometry_and_garment_parts() -> None:
    reference = _png()
    listing, pngs = make_candidate(
        images=[("front", reference, ImageRole.PRODUCT)],
        title="WILLY CHAVARRIA long sleeve",
        description="cotton cutsew",
    )
    hyp = make_hypothesis(category="garment")
    enriched = enrich_candidate(listing, pngs, category="garment")
    match = match_candidate(
        hypothesis=hyp,
        candidate=enriched,
        reference_pngs={"user": reference},
        reference_descriptors=prepare_reference({"user": reference}),
    )
    assert match.geometry.interval.mean >= 0.92
    assert any(
        "correspondence" in item and "-inliers" in item for item in match.explanation.support
    )
    pair = correspond_pair(reference, reference)
    assert pair.inlier_count >= CORRESPONDENCE_STRONG_INLIERS
    assert any(item.correspondence_ref for item in match.part_correspondence)
    assert part_matches_are_not_footwear(match.part_correspondence)


def part_matches_are_not_footwear(parts: list[object]) -> bool:
    names = {getattr(item, "part_name", "") for item in parts}
    return not names & {"eyelets", "outsole", "heel", "lateral_panels"}


def test_apply_category_rewrites_orchestrator_views_for_a_garment() -> None:
    listing, pngs = make_candidate(images=[("shot", _png(), ImageRole.PRODUCT)])
    # Orchestrator path: no category, structure refine may invent a heel.
    enriched = enrich_candidate(listing, pngs)
    apply_category(enriched, "garment")
    views = {guess.view for guess in enriched.views}
    assert ViewHypothesis.HEEL not in views
    assert ViewHypothesis.SOLE not in views
    assert ViewHypothesis.FRONT in views or ViewHypothesis.DETAIL in views
    assert all(part.name != "eyelets" for part in enriched.parts)


def test_text_identity_reads_seller_reported_brand() -> None:
    listing, pngs = make_candidate(
        title="無地 ロングスリーブカットソー",
        description="cotton",
        images=[("front", _png(), ImageRole.PRODUCT)],
    )
    listing = listing.model_copy(
        update={
            "seller_reported_model": None,
            "seller_reported_brand": classified(
                "House Name", FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER
            ),
        }
    )
    hyp = make_hypothesis(category="garment")
    enriched = enrich_candidate(listing, pngs, category="garment")
    match = match_candidate(
        hypothesis=hyp,
        candidate=enriched,
        reference_pngs={"user": _png()},
        reference_descriptors=prepare_reference({"user": _png()}),
    )
    assert match.text_identity.interval.mean >= 0.4


def test_correspondence_backed_combination_does_not_need_embedding_0_88() -> None:
    term = scored(0.81, spread=0.05, support=["ev:correspondence:orb:16-inliers"])
    global_term = scored(0.81, spread=0.05)
    interval = combine_item_match(
        text=scored(0.9, spread=0.04),
        global_visual=global_term,
        parts_mean=0.95,
        geometry=term,
        material=scored(0.9, spread=0.04),
        cross=scored(0.9, spread=0.04),
        hard_count=0,
        missing_count=1,
    )
    # The lift may tighten the lower bound up to the mean; it must not require
    # the embedding term to reach 0.88, and it must not move the gate.
    assert interval.mean >= 0.85
    assert interval.lower_bound <= interval.mean


def test_garment_authenticity_is_uncalibrated_so_real_is_out_of_reach() -> None:
    hyp = make_hypothesis(category="garment")
    listing, pngs = make_candidate(
        title="無地 ロングスリーブカットソー",
        description="cotton cutsew",
        images=[
            ("front", _png(), ImageRole.PRODUCT),
            ("rear", _png(colour=(30, 30, 30)), ImageRole.PRODUCT),
            ("detail", _png(colour=(40, 20, 20), shift=8), ImageRole.PRODUCT),
        ],
    )
    views = [
        ViewGuess("front", ViewHypothesis.FRONT, 0.8, "test"),
        ViewGuess("rear", ViewHypothesis.REAR, 0.7, "test"),
        ViewGuess("detail", ViewHypothesis.DETAIL, 0.7, "test"),
        ViewGuess("label", ViewHypothesis.LABEL, 0.7, "test"),
        ViewGuess("lateral", ViewHypothesis.LATERAL, 0.5, "test"),
    ]
    from searcher.matching.types import EnrichedCandidate

    enriched = EnrichedCandidate(
        candidate=listing,
        pngs=pngs,
        views=views,
        descriptors={
            "front": _descriptor("front", area=0.64),
            "rear": _descriptor("rear", area=0.60),
            "detail": _descriptor("detail", area=0.20, aspect=1.1),
        },
        isolated=[_subject("front"), _subject("rear", 0.6), _subject("detail", 0.2)],
    )
    auth = assess_authenticity(
        hypothesis=hyp,
        candidate=enriched,
        reference_descriptors={"front": _descriptor("ref")},
    )
    assert auth.authority_ceiling.startswith("uncalibrated")
    assert auth.authenticity_distribution.lower_bound < 0.80
    profile = profile_for("garment")
    complete, _missing = completeness(profile=profile, present_views=set(profile.expected_views))
    assert complete == 1.0
    match = match_candidate(
        hypothesis=hyp,
        candidate=enrich_candidate(listing, pngs, category="garment"),
        reference_pngs={"user": _png()},
        reference_descriptors=prepare_reference({"user": _png()}),
    )
    decision = route_candidate(
        candidate=listing,
        match=match,
        authenticity=auth,
        utility=listing_utility(listing, destination_verified=True),
        completeness_value=complete,
        destination_verified=True,
        policy=load_policy("matching-1"),
    )
    # Uncalibrated authenticity cannot satisfy matching-1 Real, even with
    # complete views. Labels, logos and provenance are also missing.
    assert decision.decision.public is not BucketPublic.REAL
    short = {
        "authority_ceiling": auth.authority_ceiling,
        "auth_lower": auth.authenticity_distribution.lower_bound,
        "labels_missing": auth.label_and_code_consistency.missing,
        "logos_missing": auth.logo_and_hardware_consistency.missing,
        "provenance_missing": auth.provenance_signal.missing,
    }
    assert "label-view" in short["labels_missing"] or "reference-label" in short["labels_missing"]
    assert "logo-not-resolved" in short["logos_missing"] or "logo-view" in short["logos_missing"]
    assert "provenance" in short["provenance_missing"]


def test_footwear_true_match_can_still_be_real() -> None:
    hyp = make_hypothesis()
    ref = render_views(REFERENCE_SHOE)
    candidate, pngs = make_candidate(images=views_for(REFERENCE_SHOE))
    enriched = enrich_candidate(candidate, pngs)
    match = match_candidate(
        hypothesis=hyp,
        candidate=enriched,
        reference_pngs=ref,
        reference_descriptors=prepare_reference(ref),
        constraints=constraints(),
    )
    auth = assess_authenticity(
        hypothesis=hyp,
        candidate=enriched,
        reference_descriptors=prepare_reference(ref),
        constraints=constraints(),
    )
    decision = route_candidate(
        candidate=candidate,
        match=match,
        authenticity=auth,
        utility=listing_utility(candidate, destination_verified=True),
        completeness_value=0.7,
        constraints=constraints(),
        destination_verified=True,
        policy=load_policy("matching-1"),
    )
    assert decision.decision.public is BucketPublic.REAL
    assert match.item_match_distribution.lower_bound >= 0.90
    assert auth.authenticity_distribution.lower_bound >= 0.80


_KIND = Path("fixtures/known_item_kind/images")
_SNAP = Path("fixtures/user_snapshots")


@pytest.mark.skipif(
    not (_SNAP / "8001001141404_snapshot.jpg").is_file(),
    reason="user_snapshots fixture is not materialized in this checkout",
)
def test_kind_target_cites_correspondence_and_cannot_reach_real() -> None:
    """Reproduce the flagship Kind listing (handle 8001001141404).

    Run this test file with pytest; this case is skipped if fixtures are absent.
    """
    handle = "8001001141404"
    snap = (_SNAP / f"{handle}_snapshot.jpg").read_bytes()
    listing_files = sorted(_KIND.glob(f"{handle}_*.jpg"))
    assert listing_files
    listing, pngs = make_candidate(
        images=[(path.stem, path.read_bytes(), ImageRole.PRODUCT) for path in listing_files],
        title="無地 ロングスリーブカットソー",
        description="WILLY CHAVARRIA long sleeve cutsew",
    )
    hyp = make_hypothesis(category="garment")
    listing = listing.model_copy(
        update={
            "seller_reported_brand": classified(
                "WILLY CHAVARRIA", FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER
            )
        }
    )
    enriched = enrich_candidate(listing, pngs, category="garment")
    match = match_candidate(
        hypothesis=hyp,
        candidate=enriched,
        reference_pngs={"user": snap},
        reference_descriptors=prepare_reference({"user": snap}),
    )
    auth = assess_authenticity(
        hypothesis=hyp,
        candidate=enriched,
        reference_descriptors=prepare_reference({"user": snap}),
    )
    cites = [item for item in match.explanation.support if "correspondence" in item]
    assert cites
    assert any("-inliers" in item for item in cites)
    assert match.item_match_distribution.lower_bound < 0.90
    assert auth.authority_ceiling.startswith("uncalibrated")
    assert auth.authenticity_distribution.lower_bound < 0.80
    decision = route_candidate(
        candidate=listing,
        match=match,
        authenticity=auth,
        utility=listing_utility(listing, destination_verified=True),
        completeness_value=0.80,
        destination_verified=True,
        policy=load_policy("matching-1"),
    )
    assert decision.decision.public is not BucketPublic.REAL
