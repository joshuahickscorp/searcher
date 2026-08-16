"""Fixture campaign walks the real state machine offline."""

from __future__ import annotations

from searcher.campaigns.resume import reconstruct
from searcher.campaigns.runner import FixtureRunner
from searcher.contracts.enums import BucketPublic, CampaignState


def test_dior_minimal_reaches_complete(controller: object) -> None:
    runner = FixtureRunner(controller)  # type: ignore[arg-type]
    intent = runner.create("dior_minimal")
    runner.run(intent.search_id)
    campaign = controller.get(intent.search_id)  # type: ignore[attr-defined]
    assert campaign.state is CampaignState.COMPLETE
    snap = reconstruct(controller.repos, intent.search_id)  # type: ignore[attr-defined]
    assert snap.accepted_evidence_ids
    assert snap.active_hypotheses
    assert snap.completed_queries
    assert snap.normalized_candidates
    assert snap.fetched_pages
    publics = {d.decision.public for d in snap.result_state}
    assert BucketPublic.REAL in publics
    assert BucketPublic.POSSIBLY_REAL in publics
    assert BucketPublic.HIDDEN in publics
    sold = [c for c in snap.normalized_candidates if c.availability.value == "SOLD"]
    assert sold
    sold_decisions = [d for d in snap.result_state if d.candidate_id == sold[0].candidate_id]
    assert sold_decisions
    assert sold_decisions[0].decision.public is not BucketPublic.REAL
