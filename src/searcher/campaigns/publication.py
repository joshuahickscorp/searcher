"""Map an internal bucket decision onto the public result lists."""

from __future__ import annotations

from searcher.contracts.enums import BucketPublic, PublicEventName, SourceFamily
from searcher.contracts.models import BucketDecision, ListingCandidate
from searcher.ranking.vetoes import SELF_DECLARED_REPLICA
from searcher.retrieval.text import self_declared_replica
from searcher.sources.families import REPLICA_SOURCE_REASON, family_for


def _listing_text(candidate: ListingCandidate | None) -> str:
    if candidate is None:
        return ""
    parts: list[str] = []
    for fact in (candidate.title, candidate.description):
        if fact is not None and fact.value:
            parts.append(str(fact.value))
    return " ".join(parts)


def is_replica_result(
    candidate: ListingCandidate | None,
    decision: BucketDecision,
) -> bool:
    """Replica-family or self-declared replica listings never enter Real."""
    if candidate is not None and family_for(candidate.source_adapter) is SourceFamily.REPLICA:
        return True
    codes = list(decision.hard_vetoes) + list(decision.reason_codes)
    if SELF_DECLARED_REPLICA in codes or REPLICA_SOURCE_REASON in codes:
        return True
    return self_declared_replica(_listing_text(candidate))


def published_public_bucket(
    decision: BucketDecision,
    candidate: ListingCandidate | None,
) -> str:
    if is_replica_result(candidate, decision):
        return BucketPublic.REPLICA.value
    return decision.decision.public.value


def event_name_for_public_bucket(bucket: str) -> str:
    if bucket == BucketPublic.REAL.value:
        return PublicEventName.RESULT_REAL.value
    if bucket == BucketPublic.POSSIBLY_REAL.value:
        return PublicEventName.RESULT_POSSIBLY_REAL.value
    if bucket == BucketPublic.REPLICA.value:
        return PublicEventName.RESULT_REPLICA.value
    return PublicEventName.RESULT_REMOVED.value
