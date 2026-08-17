"""Versioned Real / Possibly Real gates."""

from __future__ import annotations

from tests.helpers_matching import constraints, make_candidate, make_hypothesis, views_for

from searcher.authenticity.engine import assess_authenticity
from searcher.contracts.enums import Availability, BucketPublic
from searcher.contracts.models import SearchConstraints
from searcher.matching.pipeline import enrich_candidate, match_candidate, prepare_reference
from searcher.matching.synth import ADJACENT_SHOE, REFERENCE_SHOE, render_views
from searcher.ranking.buckets import route_candidate
from searcher.ranking.policy_versions import load_policy
from searcher.ranking.utility import listing_utility


def _judge(spec, **kwargs):  # type: ignore[no-untyped-def]
    hyp = make_hypothesis()
    ref = render_views(REFERENCE_SHOE)
    candidate, pngs = make_candidate(images=views_for(spec), **kwargs)
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
    utility = listing_utility(candidate, destination_verified=True)
    decision = route_candidate(
        # Theft and stock-photo screening ran and found nothing. Real is
        # fail-closed without this, because the veto cannot fire unscreened.
        photo_screening_ran=True,
        candidate=candidate,
        match=match,
        authenticity=auth,
        utility=utility,
        completeness_value=0.7,
        constraints=SearchConstraints(),
        destination_verified=True,
        policy=load_policy("matching-1"),
    )
    return decision


def test_true_match_can_be_real() -> None:
    decision = _judge(REFERENCE_SHOE)
    assert decision.decision.public is BucketPublic.REAL


def test_adjacent_is_hidden() -> None:
    decision = _judge(ADJACENT_SHOE)
    assert decision.decision.public is BucketPublic.HIDDEN
    assert "WRONG_PRODUCT" in decision.hard_vetoes


def test_dead_listing_not_real() -> None:
    decision = _judge(REFERENCE_SHOE, availability=Availability.SOLD)
    assert decision.decision.public is not BucketPublic.REAL
