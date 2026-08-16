"""Hard-veto reason codes."""

from __future__ import annotations

from searcher.contracts.enums import Availability, FactClass, FactOrigin
from searcher.contracts.models import ListingCandidate
from searcher.contracts.primitives import classified
from searcher.core.time import parse_utc
from searcher.ranking.vetoes import (
    DEAD_LISTING,
    MALICIOUS_URL,
    SELF_DECLARED_REPLICA,
    collect_hard_vetoes,
    url_is_malicious,
)

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def _cand(url: str, title: str, availability: Availability = Availability.LIVE) -> ListingCandidate:
    return ListingCandidate(
        candidate_id="c",
        canonical_url=url,
        source_adapter="fixture",
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=availability,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )


def test_malicious_schemes() -> None:
    assert url_is_malicious("javascript:alert(1)")
    assert url_is_malicious("file:///etc/passwd")
    assert url_is_malicious("http://127.0.0.1/x")
    assert not url_is_malicious("https://fixture.example/item")


def test_replica_language_is_a_veto() -> None:
    vetoes = collect_hard_vetoes(
        candidate=_cand("https://fixture.example/r", "Field Model replica 1:1"),
        item_hard=[],
        auth_hard=["self-declared-replica"],
        item_lower=0.9,
        destination_verified=True,
        stolen_photo=False,
        duplicate_no_utility=False,
        dead_listing_is_hard_veto=True,
        plausible_floor=0.45,
        exact_colour_required=False,
    )
    assert SELF_DECLARED_REPLICA in vetoes


def test_dead_listing_reason() -> None:
    vetoes = collect_hard_vetoes(
        candidate=_cand("https://fixture.example/r", "Field Model", Availability.SOLD),
        item_hard=[],
        auth_hard=[],
        item_lower=0.9,
        destination_verified=True,
        stolen_photo=False,
        duplicate_no_utility=False,
        dead_listing_is_hard_veto=True,
        plausible_floor=0.45,
        exact_colour_required=False,
    )
    assert DEAD_LISTING in vetoes
    assert MALICIOUS_URL not in vetoes
