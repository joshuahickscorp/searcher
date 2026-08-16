"""Property: a hard veto bars both public tabs."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import Availability, BucketPublic, FactClass, FactOrigin
from searcher.contracts.models import (
    AuthenticityEvidence,
    ListingCandidate,
    MatchEvidence,
    SearchConstraints,
)
from searcher.contracts.primitives import ScoreInterval, ScoreWithEvidence, classified
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.ranking.buckets import route_candidate
from searcher.ranking.policy_versions import load_policy
from searcher.ranking.utility import listing_utility

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def _score() -> ScoreWithEvidence:
    return ScoreWithEvidence(interval=ScoreInterval(mean=0.95, lower_bound=0.92, upper_bound=0.98))


def _match(cid: str, hard: list[str]) -> MatchEvidence:
    interval = ScoreInterval(mean=0.95, lower_bound=0.92, upper_bound=0.98)
    return MatchEvidence(
        match_evidence_id=new_id(),
        candidate_id=cid,
        hypothesis_id="h",
        global_visual=_score(),
        text_identity=_score(),
        geometry=_score(),
        material=_score(),
        colourway=_score(),
        cross_image_consistency=_score(),
        metadata_consistency=_score(),
        hard_contradictions=hard,
        item_match_distribution=interval,
    )


def _auth(cid: str, hard: list[str]) -> AuthenticityEvidence:
    interval = ScoreInterval(mean=0.9, lower_bound=0.85, upper_bound=0.95)
    return AuthenticityEvidence(
        authenticity_evidence_id=new_id(),
        candidate_id=cid,
        reference_class="designer_footwear",
        construction_consistency=_score(),
        label_and_code_consistency=_score(),
        logo_and_hardware_consistency=_score(),
        material_consistency=_score(),
        photo_set_consistency=_score(),
        image_originality=_score(),
        source_and_seller_signal=_score(),
        provenance_signal=_score(),
        price_anomaly=_score(),
        hard_contradictions=hard,
        authenticity_distribution=interval,
        authority_ceiling="fixture-calibrated:fixture-v1",
    )


@given(st.sampled_from(["javascript:x", "file:///tmp", "http://127.0.0.1/x"]))
def test_malicious_url_is_hidden(url: str) -> None:
    cid = new_id()
    candidate = ListingCandidate(
        candidate_id=cid,
        canonical_url=url,
        source_adapter="t",
        title=classified("ok", FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )
    decision = route_candidate(
        candidate=candidate,
        match=_match(cid, []),
        authenticity=_auth(cid, []),
        utility=listing_utility(candidate, destination_verified=True),
        completeness_value=0.9,
        constraints=SearchConstraints(),
        destination_verified=True,
        policy=load_policy("matching-1"),
    )
    assert decision.decision.public is BucketPublic.HIDDEN
    assert decision.hard_vetoes


@given(st.lists(st.sampled_from(["eyelet-count-mismatch", "panel-count-mismatch"]), min_size=1))
def test_item_hard_mismatch_hidden(hard: list[str]) -> None:
    cid = new_id()
    candidate = ListingCandidate(
        candidate_id=cid,
        canonical_url="https://fixture.example/ok",
        source_adapter="t",
        title=classified("ok", FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )
    decision = route_candidate(
        candidate=candidate,
        match=_match(cid, hard),
        authenticity=_auth(cid, []),
        utility=listing_utility(candidate, destination_verified=True),
        completeness_value=0.9,
        constraints=SearchConstraints(),
        destination_verified=True,
        policy=load_policy("matching-1"),
    )
    assert decision.decision.public is BucketPublic.HIDDEN
    assert decision.decision.public is not BucketPublic.REAL
    assert decision.decision.public is not BucketPublic.POSSIBLY_REAL
