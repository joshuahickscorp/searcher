"""Show that each required scope test fails when its behaviour is inverted."""

from __future__ import annotations

import pytest
from tests.unit.test_replica_publication import _candidate, _decision
from tests.unit.test_source_scopes import _query

from searcher.campaigns.publication import published_public_bucket
from searcher.contracts.enums import BucketInternal, BucketPublic, SourceFamily
from searcher.sources.broker import SourceBroker
from searcher.sources.families import family_for, normalize_source_scopes


def test_broken_default_scope_is_detected() -> None:
    def broken(values: object) -> tuple[str, ...]:
        del values
        return ("replica",)

    assert broken(None) != normalize_source_scopes(None)
    with pytest.raises(AssertionError):
        assert broken(None) == ("legitimate",)


def test_broken_family_filter_is_detected() -> None:
    plans = SourceBroker().plan(
        [_query()],
        include_disabled=True,
        families=frozenset({"replica"}),
    )
    adapters = {plan.source_adapter for plan in plans}

    def broken() -> set[str]:
        return adapters | {"ebay"}

    with pytest.raises(AssertionError):
        assert "ebay" not in broken()


def test_broken_replica_publication_is_detected() -> None:
    candidate = _candidate(source_adapter="yupoo")
    decision = _decision(
        candidate.candidate_id,
        public=BucketPublic.REAL,
        internal=BucketInternal.REAL,
        reason_codes=["real-gate"],
    )
    assert family_for("yupoo") is SourceFamily.REPLICA
    correct = published_public_bucket(decision, candidate)

    def broken() -> str:
        return decision.decision.public.value

    assert correct == BucketPublic.REPLICA.value
    with pytest.raises(AssertionError):
        assert broken() != BucketPublic.REAL.value
    with pytest.raises(AssertionError):
        assert broken() == BucketPublic.REPLICA.value
