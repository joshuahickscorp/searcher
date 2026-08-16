"""Index hit never changes a bucket a fresh fetch would not also produce."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import Availability, FactClass, FactOrigin
from searcher.contracts.models import (
    AuthenticityEvidence,
    BucketDecision,
    ListingCandidate,
    ListingUtility,
    MatchEvidence,
)
from searcher.contracts.primitives import ScoreInterval, ScoreWithEvidence, classified
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.index.keys import versions_from_settings
from searcher.index.store import WarmIndex
from searcher.ranking.buckets import route_candidate
from searcher.ranking.utility import listing_utility
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate
from searcher.storage.repositories import Repositories


def _score(mean: float, lower: float, upper: float) -> ScoreWithEvidence:
    return ScoreWithEvidence(
        interval=ScoreInterval(mean=mean, lower_bound=lower, upper_bound=upper)
    )


def _match(cid: str, mean: float, lower: float, upper: float) -> MatchEvidence:
    interval = ScoreInterval(mean=mean, lower_bound=lower, upper_bound=upper)
    return MatchEvidence(
        match_evidence_id=new_id(),
        candidate_id=cid,
        hypothesis_id="h",
        global_visual=_score(mean, lower, upper),
        text_identity=_score(mean, lower, upper),
        geometry=_score(mean, lower, upper),
        material=_score(mean, lower, upper),
        colourway=_score(mean, lower, upper),
        cross_image_consistency=_score(mean, lower, upper),
        metadata_consistency=_score(mean, lower, upper),
        item_match_distribution=interval,
    )


def _auth(cid: str, mean: float, lower: float, upper: float) -> AuthenticityEvidence:
    interval = ScoreInterval(mean=mean, lower_bound=lower, upper_bound=upper)
    return AuthenticityEvidence(
        authenticity_evidence_id=new_id(),
        candidate_id=cid,
        reference_class="designer_footwear",
        construction_consistency=_score(mean, lower, upper),
        label_and_code_consistency=_score(mean, lower, upper),
        logo_and_hardware_consistency=_score(mean, lower, upper),
        material_consistency=_score(mean, lower, upper),
        photo_set_consistency=_score(mean, lower, upper),
        image_originality=_score(mean, lower, upper),
        source_and_seller_signal=_score(mean, lower, upper),
        provenance_signal=_score(mean, lower, upper),
        price_anomaly=_score(0.5, 0.5, 0.5),
        authenticity_distribution=interval,
        authority_ceiling="fixture-calibrated:fixture-v1",
    )


def _ordered_interval(data: st.DataObject) -> tuple[float, float, float]:
    lower = data.draw(st.floats(0.2, 0.85, allow_nan=False, allow_infinity=False))
    span = data.draw(st.floats(0.02, 0.14, allow_nan=False, allow_infinity=False))
    upper = min(1.0, lower + span)
    mean = (lower + upper) / 2.0
    return mean, lower, upper


@given(st.data())
def test_index_hit_preserves_bucket_and_never_raises(data: st.DataObject) -> None:
    item_mean, item_lo, item_hi = _ordered_interval(data)
    auth_mean, auth_lo, auth_hi = _ordered_interval(data)
    completeness = data.draw(st.floats(0.3, 0.9, allow_nan=False, allow_infinity=False))
    cid = new_id()
    now = utc_now()
    candidate = ListingCandidate(
        candidate_id=cid,
        canonical_url="https://fixture.local/item/index-prop",
        source_adapter="fixture",
        title=classified("House Name Field Model", FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=now,
        last_checked_at=now,
    )
    match = _match(cid, item_mean, item_lo, item_hi)
    auth = _auth(cid, auth_mean, auth_lo, auth_hi)
    utility = listing_utility(candidate, destination_verified=True)
    fresh = route_candidate(
        candidate=candidate,
        match=match,
        authenticity=auth,
        utility=utility,
        completeness_value=completeness,
        destination_verified=True,
        live_checked=True,
    )
    database = Database(":memory:")
    migrate(database)
    try:
        _run_index_bucket_case(
            database,
            candidate=candidate,
            match=match,
            auth=auth,
            utility=utility,
            fresh=fresh,
            item_mean=item_mean,
            item_lo=item_lo,
            item_hi=item_hi,
            auth_mean=auth_mean,
            auth_lo=auth_lo,
            auth_hi=auth_hi,
            completeness=completeness,
        )
    finally:
        database.close()


def _run_index_bucket_case(
    database: Database,
    *,
    candidate: ListingCandidate,
    match: MatchEvidence,
    auth: AuthenticityEvidence,
    utility: ListingUtility,
    fresh: BucketDecision,
    item_mean: float,
    item_lo: float,
    item_hi: float,
    auth_mean: float,
    auth_lo: float,
    auth_hi: float,
    completeness: float,
) -> None:
    repos = Repositories(database)
    index = WarmIndex(repos)
    versions = versions_from_settings()
    listing_key = index.put_listing(candidate, versions)
    index.put_evidence(
        listing_key=listing_key,
        hypothesis_digest="hyp-1",
        versions=versions,
        item_match_mean=item_mean,
        item_match_lower=item_lo,
        item_match_upper=item_hi,
        authenticity_mean=auth_mean,
        authenticity_lower=auth_lo,
        authenticity_upper=auth_hi,
        completeness=completeness,
        destination_verified=True,
        hard_vetoes=list(fresh.hard_vetoes),
        match_payload=match.model_dump(mode="json"),
        authenticity_payload=auth.model_dump(mode="json"),
    )
    loaded = index.get_evidence(listing_key, "hyp-1", versions)
    assert loaded is not None
    assert loaded.item_match_lower == item_lo
    assert loaded.authenticity_lower == auth_lo
    assert loaded.item_match_mean == item_mean
    replay_match = MatchEvidence.model_validate(loaded.match_payload)
    replay_auth = AuthenticityEvidence.model_validate(loaded.authenticity_payload)
    replay = route_candidate(
        candidate=candidate,
        match=replay_match,
        authenticity=replay_auth,
        utility=utility,
        completeness_value=loaded.completeness,
        destination_verified=loaded.destination_verified,
        live_checked=True,
    )
    assert replay.decision.public == fresh.decision.public
    assert replay.item_match_lower_bound == fresh.item_match_lower_bound
    assert replay.authenticity_lower_bound == fresh.authenticity_lower_bound
    assert replay.item_match_lower_bound <= item_lo + 1e-12
    assert replay.authenticity_lower_bound <= auth_lo + 1e-12
