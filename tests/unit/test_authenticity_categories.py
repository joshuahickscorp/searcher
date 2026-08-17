"""Category authenticity is a measurement, not a footwear bin reused on shirts."""

from __future__ import annotations

import json
import re

from tests.helpers_matching import make_candidate, make_hypothesis

from searcher.authenticity.calibration import CalibrationTable, table_applies
from searcher.authenticity.completeness import completeness
from searcher.authenticity.construction import assess_construction
from searcher.authenticity.engine import assess_authenticity
from searcher.authenticity.established import (
    UNESTABLISHED_CONSTRUCTION,
    published_compare_parts,
)
from searcher.authenticity.profiles import GARMENT_PROFILE, profile_for
from searcher.contracts.enums import FactClass, ViewHypothesis
from searcher.contracts.models import AuthenticityEvidence, MatchEvidence
from searcher.contracts.primitives import PublicExplanation, ScoreInterval, ScoreWithEvidence
from searcher.core.ids import new_id
from searcher.matching.types import EnrichedCandidate, StructuredDescriptor, ViewGuess
from searcher.ranking.buckets import route_candidate
from searcher.ranking.policy_versions import load_policy
from searcher.ranking.questions import answer_questions
from searcher.ranking.utility import listing_utility


def _descriptor(image_id: str, *, eyelets: int = 6) -> StructuredDescriptor:
    return StructuredDescriptor(
        image_id=image_id,
        width=1024,
        height=1024,
        aspect=0.7,
        subject_area=0.62,
        centroid=(0.5, 0.5),
        eyelet_count=eyelets,
        panel_count=4,
        seam_count=3,
        outsole_ratio=0.41,
        sole_to_upper=0.5,
        heel_aspect=0.3,
        heel_cut="rounded",
        heel_angle=0.2,
        logo_xy=None,
        logo_kind=None,
        tread_kind="none",
        label_hash=None,
        dominant_rgb=(18.0, 18.0, 18.0),
        smoothness=0.35,
        keypoints=90,
    )


def _has_part(blob: str, part: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(part)}(?![a-z0-9])", blob) is not None


def _score() -> ScoreWithEvidence:
    return ScoreWithEvidence(interval=ScoreInterval(mean=0.9, lower_bound=0.86, upper_bound=0.94))


def test_garment_profile_is_not_footwear() -> None:
    profile = profile_for("garment")
    assert profile.profile_id == GARMENT_PROFILE.profile_id
    assert profile.category == "garment"
    assert "heel" not in profile.expected_views
    assert "sole" not in profile.expected_views
    assert "eyelets" not in profile.established_parts
    assert "outsole" not in profile.established_parts
    assert "collar" in profile.established_parts
    assert profile.construction_checks == ()


def test_shirt_aliases_use_the_garment_profile() -> None:
    for key in ("shirt", "long-sleeve", "cutsew", "clothing"):
        assert profile_for(key).profile_id == "designer_garment"


def test_garment_construction_is_unestablished_even_when_descriptors_have_shoe_fields() -> None:
    score, hard, _soft = assess_construction(
        profile=profile_for("garment"),
        reference=_descriptor("ref", eyelets=8),
        candidate=_descriptor("cand", eyelets=4),
    )
    assert score.fact_class is FactClass.UNRESOLVED
    assert UNESTABLISHED_CONSTRUCTION in score.missing
    assert hard == []
    blob = json.dumps(score.model_dump(mode="json")).lower()
    assert not _has_part(blob, "eyelet")
    assert not _has_part(blob, "outsole")
    assert not _has_part(blob, "heel")


def test_footwear_construction_still_measures_eyelets() -> None:
    _score_row, hard, _soft = assess_construction(
        profile=profile_for("footwear"),
        reference=_descriptor("ref", eyelets=8),
        candidate=_descriptor("cand", eyelets=4),
    )
    assert "construction-eyelet-count" in hard


def test_footwear_calibration_table_does_not_apply_to_a_garment() -> None:
    table = CalibrationTable(
        profile="designer_footwear",
        version="fixture-v1",
        method="test",
        provenance={},
        bins=((0.0, 1.0, 0.5, 0.1),),
    )
    assert table_applies(table, profile_for("footwear").profile_id)
    assert not table_applies(table, profile_for("garment").profile_id)


def test_published_garment_payload_has_no_shoe_parts() -> None:
    hyp = make_hypothesis(category="garment")
    listing, pngs = make_candidate(
        title="plain long sleeve cutsew",
        description="black cotton, no box",
    )
    views = [
        ViewGuess("front", ViewHypothesis.FRONT, 0.8, "test"),
        ViewGuess("label", ViewHypothesis.LABEL, 0.7, "test"),
        ViewGuess("detail", ViewHypothesis.DETAIL, 0.7, "test"),
    ]
    descriptors = {
        "front": _descriptor("front"),
        "label": _descriptor("label"),
        "detail": _descriptor("detail"),
    }
    enriched = EnrichedCandidate(
        candidate=listing,
        pngs=pngs,
        views=views,
        descriptors=descriptors,
    )
    auth = assess_authenticity(
        hypothesis=hyp,
        candidate=enriched,
        reference_descriptors={"front": _descriptor("ref")},
    )
    assert auth.reference_class == "designer_garment"
    assert auth.authority_ceiling.startswith("uncalibrated")
    assert auth.construction_consistency.fact_class is FactClass.UNRESOLVED
    assert UNESTABLISHED_CONSTRUCTION in auth.missing_evidence
    match = MatchEvidence(
        match_evidence_id=new_id(),
        candidate_id=listing.candidate_id,
        hypothesis_id=hyp.hypothesis_id,
        global_visual=_score(),
        text_identity=_score(),
        geometry=_score(),
        material=_score(),
        colourway=_score(),
        cross_image_consistency=_score(),
        metadata_consistency=_score(),
        hard_contradictions=["eyelet-count-mismatch", "outsole-geometry-mismatch"],
        missing_views=["heel", "sole", "front"],
        item_match_distribution=ScoreInterval(mean=0.9, lower_bound=0.86, upper_bound=0.94),
        explanation=PublicExplanation(support=["ev:parts:eyelets"], missing_evidence=["heel"]),
    )
    decision = route_candidate(
        candidate=listing,
        match=match,
        authenticity=auth,
        utility=listing_utility(listing, destination_verified=True),
        completeness_value=0.8,
        destination_verified=True,
        policy=load_policy("matching-1"),
    )
    answers = answer_questions(
        candidate=listing,
        match=match,
        authenticity=auth,
        utility=listing_utility(listing, destination_verified=True),
        decision=decision,
    )
    compare_parts = published_compare_parts(
        ["eyelets", "outsole", "heel", "collar"],
        profile_for("garment"),
    )
    payload = {
        "reference_class": auth.reference_class,
        "authority_ceiling": auth.authority_ceiling,
        "construction": auth.construction_consistency.model_dump(mode="json"),
        "missing_evidence": auth.missing_evidence,
        "hard_contradictions": auth.hard_contradictions,
        "decision_missing": decision.explanation.missing_evidence,
        "decision_contradictions": decision.explanation.contradictions,
        "answers": answers,
        "compare_parts": compare_parts,
    }
    blob = json.dumps(payload).lower()
    assert not _has_part(blob, "eyelet")
    assert not _has_part(blob, "eyelets")
    assert not _has_part(blob, "outsole")
    assert not _has_part(blob, "heel")
    assert not _has_part(blob, "sole")
    assert any(row["status"] == "unestablished" for row in compare_parts)
    assert answers["authenticity_label_calibrated"] is False
    assert UNESTABLISHED_CONSTRUCTION in answers["missing_evidence"]


def test_garment_completeness_does_not_demand_shoe_views() -> None:
    profile = profile_for("garment")
    value, missing = completeness(
        profile=profile,
        present_views=set(profile.expected_views),
    )
    assert value == 1.0
    assert missing == []
    assert "heel" not in profile.expected_views
    assert "sole" not in profile.expected_views


def test_unestablished_fields_are_the_ones_removed_from_the_measurement() -> None:
    """Construction is no longer a 0.5 footwear bin for a shirt.

    Fields marked unestablished rather than invented:
    - construction_consistency (no garment construction matcher)
    - footwear calibration / public authenticity percentage
    - eyelets, outsole, heel, tongue, midsole as compare parts
    """
    auth = AuthenticityEvidence(
        authenticity_evidence_id=new_id(),
        candidate_id="c",
        reference_class="designer_garment",
        construction_consistency=ScoreWithEvidence(
            interval=ScoreInterval(mean=0.5, lower_bound=0.25, upper_bound=0.75),
            missing=[UNESTABLISHED_CONSTRUCTION],
            fact_class=FactClass.UNRESOLVED,
        ),
        label_and_code_consistency=_score(),
        logo_and_hardware_consistency=_score(),
        material_consistency=_score(),
        photo_set_consistency=_score(),
        image_originality=_score(),
        source_and_seller_signal=_score(),
        provenance_signal=_score(),
        price_anomaly=_score(),
        missing_evidence=[UNESTABLISHED_CONSTRUCTION],
        authenticity_distribution=ScoreInterval(mean=0.5, lower_bound=0.28, upper_bound=0.72),
        authority_ceiling="uncalibrated",
    )
    assert auth.construction_consistency.fact_class is FactClass.UNRESOLVED
    assert auth.authority_ceiling == "uncalibrated"
    payload = auth.model_dump(mode="json")
    blob = json.dumps(payload).lower()
    assert not _has_part(blob, "eyelet")
    assert not _has_part(blob, "outsole")
    assert not _has_part(blob, "heel")
