"""Map an internal bucket decision onto the public result lists."""

from __future__ import annotations

from urllib.parse import urlparse

from searcher.contracts.enums import (
    BucketPublic,
    CampaignState,
    PublicEventName,
    SourceFamily,
    SourceOutcome,
)
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


def has_usable_listing_link(candidate: ListingCandidate | None) -> bool:
    """A public result must be openable.

    Publishing a card a reader cannot click is worse than not publishing it:
    the whole product is "here is where to find this". An adversarial pass
    published a Possibly Real result with a null link and no reason codes, and
    another with a javascript: URL that the interface then refused to render.
    """
    if candidate is None:
        return False
    parsed = urlparse(str(candidate.canonical_url or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def published_public_bucket(
    decision: BucketDecision,
    candidate: ListingCandidate | None,
) -> str:
    if is_replica_result(candidate, decision):
        return BucketPublic.REPLICA.value
    public = decision.decision.public.value
    if public in {BucketPublic.REAL.value, BucketPublic.POSSIBLY_REAL.value} and not (
        decision.reason_codes or decision.hard_vetoes
    ):
        # Every published result states why it is where it is. A row with no
        # reason codes at all cannot, so it stays hidden rather than appearing
        # as a claim nobody can interrogate.
        return BucketPublic.HIDDEN.value
    if public in {BucketPublic.REAL.value, BucketPublic.POSSIBLY_REAL.value} and (
        not has_usable_listing_link(candidate)
    ):
        # Nothing to open, so nothing to publish. It stays hidden and counted,
        # which is the honest outcome rather than a card that goes nowhere.
        return BucketPublic.HIDDEN.value
    return public


# Outcomes that mean a planned source did not answer. A campaign carrying any of
# these has not exhausted the search it planned, whatever else it achieved.
_COVERAGE_UNRESOLVED = frozenset(
    {
        SourceOutcome.NETWORK_FAILED.value,
        SourceOutcome.PARSER_FAILED.value,
        SourceOutcome.RATE_LIMITED.value,
        SourceOutcome.SOURCE_UNAVAILABLE.value,
        SourceOutcome.UNMEASURABLE.value,
        SourceOutcome.NOT_ATTEMPTED.value,
    }
)


def published_terminal_status(
    *,
    proposed: str,
    pages_fetched: int,
    candidate_count: int,
    queries_compiled: int | None = None,
    saturation: bool = False,
    source_outcomes: dict[str, str] | None = None,
) -> str:
    """COMPLETE is a coverage claim. Fetching nothing is not coverage.

    A campaign that never retrieved a page and never stored a candidate cannot
    have exhausted search. Saturation (enough Real results) is a different,
    evidence-backed reason to stop. Fallbacks must not produce COMPLETE.
    """
    if proposed != CampaignState.COMPLETE.value:
        return proposed
    if saturation:
        return proposed
    if queries_compiled is not None and queries_compiled <= 0:
        return CampaignState.BLOCKED.value
    if pages_fetched <= 0 and candidate_count <= 0:
        return CampaignState.BLOCKED.value
    if source_outcomes is not None:
        # COMPLETE says the planned search was carried out. A source that timed
        # out, hung, looped on redirects, returned unparseable content, or was
        # never reached did not answer, and a campaign carrying any of those has
        # not exhausted its coverage. Fault injection found COMPLETE returned
        # after a 21.5s timeout, a 20.4s hang, a 9.8s redirect loop, and an
        # HTTP 200 whose body could not be parsed. PARTIAL is the honest word
        # for searched-but-incomplete, and the coverage map already records
        # which source it was.
        unresolved = sorted(
            name
            for name, outcome in source_outcomes.items()
            if outcome in _COVERAGE_UNRESOLVED
        )
        if unresolved:
            return CampaignState.PARTIAL.value
    return proposed


def event_name_for_public_bucket(bucket: str) -> str:
    if bucket == BucketPublic.REAL.value:
        return PublicEventName.RESULT_REAL.value
    if bucket == BucketPublic.POSSIBLY_REAL.value:
        return PublicEventName.RESULT_POSSIBLY_REAL.value
    if bucket == BucketPublic.REPLICA.value:
        return PublicEventName.RESULT_REPLICA.value
    return PublicEventName.RESULT_REMOVED.value
