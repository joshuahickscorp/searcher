"""Seller-metadata signals: exercised, and held to "never decisive".

`assess_source` is where a young account, an off-platform payment demand and a
platform "authenticated" badge are turned into evidence. The §32.1 branch floor
measurement found every one of those branches uncovered - the module sat at 50%
branch coverage - so the rules that decide how much a badge is worth had no
test at all. These assert the behaviour, not merely the lines.
"""

from __future__ import annotations

from typing import Any

from searcher.authenticity.source_signals import assess_source
from searcher.contracts.enums import Availability, FactClass, FactOrigin
from searcher.contracts.models import ListingCandidate
from searcher.contracts.primitives import classified
from searcher.core.ids import new_id
from searcher.core.time import parse_utc

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def _candidate(*, title: str = "plain long sleeve cutsew", **metadata: Any) -> ListingCandidate:
    return ListingCandidate(
        candidate_id=new_id(),
        canonical_url="https://shop.example/item/1",
        source_adapter="kind",
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        description=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
        seller_metadata=dict(metadata),
    )


def _mean(candidate: ListingCandidate) -> float:
    score, _hard, _soft = assess_source(candidate, malicious_url=False)
    return float(score.interval.mean)


def test_a_baseline_seller_scores_the_neutral_mean() -> None:
    assert _mean(_candidate()) == 0.55


def test_a_young_account_lowers_the_score() -> None:
    assert _mean(_candidate(account_age_days=3)) < _mean(_candidate())


def test_an_established_account_is_not_penalised() -> None:
    assert _mean(_candidate(account_age_days=400)) == _mean(_candidate())


def test_off_platform_payment_lowers_the_score() -> None:
    baseline = _mean(_candidate())
    for demand in ("off-platform", "wire", "crypto-only", "CRYPTO-ONLY"):
        assert _mean(_candidate(payment=demand)) < baseline, demand


def test_ordinary_payment_is_not_penalised() -> None:
    assert _mean(_candidate(payment="platform checkout")) == _mean(_candidate())


def test_a_platform_badge_is_recorded_and_changes_nothing() -> None:
    """The docstring says supportive, never decisive. Hold it to that."""
    plain = _candidate()
    badged = _candidate(authenticated=True)
    assert _mean(badged) == _mean(plain), "a platform badge must not move the score"
    score, _hard, _soft = assess_source(badged, malicious_url=False)
    support = [str(item) for item in score.support]
    assert any("platform-badge-reported" in item for item in support), (
        "the badge must still be recorded as reported evidence"
    )


def test_a_badge_cannot_rescue_a_self_declared_replica() -> None:
    badged_replica = _candidate(title="authentic replica, mirror quality", authenticated=True)
    score, hard, _soft = assess_source(badged_replica, malicious_url=False)
    assert "self-declared-replica" in hard
    assert float(score.interval.mean) <= 0.12


def test_a_malicious_url_is_a_hard_contradiction() -> None:
    score, hard, _soft = assess_source(_candidate(), malicious_url=True)
    assert "malicious-url" in hard
    assert float(score.interval.mean) <= 0.12
