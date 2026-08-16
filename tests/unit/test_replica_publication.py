"""Replica-family and self-declared replica listings cannot enter Real."""

from __future__ import annotations

from tests.conftest import make_budget, make_intent

from searcher.campaigns.events import list_events
from searcher.campaigns.orchestrator import CampaignOrchestrator
from searcher.campaigns.publication import published_public_bucket
from searcher.contracts.enums import (
    Availability,
    BucketInternal,
    BucketPublic,
    FactClass,
    FactOrigin,
    PublicEventName,
)
from searcher.contracts.models import BucketDecision, BucketDecisionFields, ListingCandidate
from searcher.contracts.primitives import classified
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.ranking.vetoes import SELF_DECLARED_REPLICA

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def _candidate(
    *,
    source_adapter: str,
    title: str = "Dior Homme General Army Trainer",
    description: str = "Used, original box.",
) -> ListingCandidate:
    return ListingCandidate(
        candidate_id=new_id(),
        canonical_url=f"https://{source_adapter}.example/item/1",
        source_adapter=source_adapter,
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        description=classified(description, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )


def _decision(
    candidate_id: str,
    *,
    public: BucketPublic,
    internal: BucketInternal,
    hard_vetoes: list[str] | None = None,
    reason_codes: list[str] | None = None,
) -> BucketDecision:
    return BucketDecision(
        candidate_id=candidate_id,
        decision=BucketDecisionFields(internal=internal, public=public),
        policy_version="matching-1",
        item_match_lower_bound=0.95,
        authenticity_lower_bound=0.90,
        evidence_completeness=0.80,
        hard_vetoes=hard_vetoes or [],
        reason_codes=reason_codes or [],
    )


def test_replica_family_with_perfect_scores_is_refused_real_and_possibly_real() -> None:
    candidate = _candidate(source_adapter="yupoo")
    decision = _decision(
        candidate.candidate_id,
        public=BucketPublic.REAL,
        internal=BucketInternal.REAL,
        reason_codes=["real-gate"],
    )
    bucket = published_public_bucket(decision, candidate)
    assert bucket == BucketPublic.REPLICA.value
    assert bucket != BucketPublic.REAL.value
    assert bucket != BucketPublic.POSSIBLY_REAL.value


def test_self_declared_replica_from_legitimate_source_is_replica_with_reason() -> None:
    candidate = _candidate(
        source_adapter="ebay",
        title="Unauthorized replica 1:1 of the original trainer",
        description="This is a replica, not authentic.",
    )
    decision = _decision(
        candidate.candidate_id,
        public=BucketPublic.HIDDEN,
        internal=BucketInternal.REJECTED,
        hard_vetoes=[SELF_DECLARED_REPLICA],
        reason_codes=[SELF_DECLARED_REPLICA, "hidden"],
    )
    assert published_public_bucket(decision, candidate) == BucketPublic.REPLICA.value
    assert SELF_DECLARED_REPLICA in decision.reason_codes
    assert SELF_DECLARED_REPLICA in decision.hard_vetoes


def test_legitimate_non_replica_stays_in_ranking_bucket() -> None:
    candidate = _candidate(source_adapter="ebay")
    decision = _decision(
        candidate.candidate_id,
        public=BucketPublic.REAL,
        internal=BucketInternal.REAL,
        reason_codes=["real-gate"],
    )
    assert published_public_bucket(decision, candidate) == BucketPublic.REAL.value


def test_orchestrator_publishes_replica_event_and_never_real(
    controller: object,
) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())  # type: ignore[attr-defined]
    search_id = intent.search_id
    replica = _candidate(source_adapter="taobao")
    declared = _candidate(
        source_adapter="the_realreal",
        title="1:1 replica of the trainer",
        description="Replica, not the authentic pair.",
    )
    genuine = _candidate(source_adapter="ebay")
    controller.repos.upsert_candidate(search_id, replica)  # type: ignore[attr-defined]
    controller.repos.upsert_candidate(search_id, declared)  # type: ignore[attr-defined]
    controller.repos.upsert_candidate(search_id, genuine)  # type: ignore[attr-defined]
    controller.repos.insert_decision(  # type: ignore[attr-defined]
        search_id,
        new_id(),
        _decision(
            replica.candidate_id,
            public=BucketPublic.REAL,
            internal=BucketInternal.REAL,
            reason_codes=["real-gate"],
        ),
    )
    controller.repos.insert_decision(  # type: ignore[attr-defined]
        search_id,
        new_id(),
        _decision(
            declared.candidate_id,
            public=BucketPublic.HIDDEN,
            internal=BucketInternal.REJECTED,
            hard_vetoes=[SELF_DECLARED_REPLICA],
            reason_codes=[SELF_DECLARED_REPLICA, "hidden"],
        ),
    )
    controller.repos.insert_decision(  # type: ignore[attr-defined]
        search_id,
        new_id(),
        _decision(
            genuine.candidate_id,
            public=BucketPublic.POSSIBLY_REAL,
            internal=BucketInternal.POSSIBLY_REAL,
            reason_codes=["possibly-real-gate"],
        ),
    )
    CampaignOrchestrator(controller)._publish(search_id)  # type: ignore[attr-defined]
    rows = {row["candidate_id"]: row for row in controller.repos.list_results(search_id)}  # type: ignore[attr-defined]
    assert rows[replica.candidate_id]["public_bucket"] == "replica"
    assert rows[declared.candidate_id]["public_bucket"] == "replica"
    assert rows[genuine.candidate_id]["public_bucket"] == "possibly_real"
    assert rows[replica.candidate_id]["public_bucket"] != "real"
    assert rows[replica.candidate_id]["public_bucket"] != "possibly_real"
    names = {event.event_name for event in list_events(controller.repos, search_id)}  # type: ignore[attr-defined]
    assert PublicEventName.RESULT_REPLICA.value in names
    assert PublicEventName.RESULT_POSSIBLY_REAL.value in names
    declared_payload = rows[declared.candidate_id]["payload"]
    assert SELF_DECLARED_REPLICA in declared_payload["reason_codes"]
    assert SELF_DECLARED_REPLICA in declared_payload["hard_vetoes"]
