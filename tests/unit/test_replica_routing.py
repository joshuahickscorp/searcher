"""Self-declared replica listings cannot enter either public tab."""

from __future__ import annotations

from searcher.contracts.enums import Availability, BucketPublic, FactClass, FactOrigin
from searcher.contracts.models import AuthenticityEvidence, ListingCandidate, MatchEvidence
from searcher.contracts.primitives import ScoreInterval, ScoreWithEvidence, classified
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.ranking.buckets import route_candidate
from searcher.ranking.policy_versions import load_policy
from searcher.ranking.utility import listing_utility
from searcher.ranking.vetoes import SELF_DECLARED_REPLICA

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def _score() -> ScoreWithEvidence:
    return ScoreWithEvidence(interval=ScoreInterval(mean=0.92, lower_bound=0.88, upper_bound=0.96))


def test_self_declared_replica_is_hidden_and_kept_as_evidence() -> None:
    cid = new_id()
    candidate = ListingCandidate(
        candidate_id=cid,
        canonical_url="https://replica.example/item/1",
        source_adapter="replica_market",
        title=classified(
            "Unauthorized replica 1:1 of the original trainer",
            FactClass.REPORTED_BY_SELLER,
            FactOrigin.SELLER,
        ),
        description=classified(
            "This is a replica, not authentic.",
            FactClass.REPORTED_BY_SELLER,
            FactOrigin.SELLER,
        ),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )
    interval = ScoreInterval(mean=0.92, lower_bound=0.88, upper_bound=0.96)
    match = MatchEvidence(
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
        item_match_distribution=interval,
    )
    auth = AuthenticityEvidence(
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
        authenticity_distribution=interval,
        authority_ceiling="fixture-calibrated:fixture-v1",
    )
    decision = route_candidate(
        candidate=candidate,
        match=match,
        authenticity=auth,
        utility=listing_utility(candidate, destination_verified=True),
        completeness_value=0.8,
        destination_verified=True,
        policy=load_policy("matching-1"),
    )
    assert decision.decision.public is BucketPublic.HIDDEN
    assert decision.decision.public is not BucketPublic.REAL
    assert decision.decision.public is not BucketPublic.POSSIBLY_REAL
    assert SELF_DECLARED_REPLICA in decision.hard_vetoes
    assert SELF_DECLARED_REPLICA in decision.reason_codes
    # Still a stored candidate — usable as identity evidence, just not public.
    assert decision.candidate_id == cid
