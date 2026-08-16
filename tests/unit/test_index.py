"""Warm index: put/get, versioned keys, TTL, isolation."""

from __future__ import annotations

from datetime import timedelta

import pytest
from tests.helpers_matching import make_hypothesis

from searcher.contracts.enums import Availability, FactClass, FactOrigin
from searcher.contracts.models import ListingCandidate
from searcher.contracts.primitives import ClassifiedFact
from searcher.core.errors import CrossCampaignAccessError
from searcher.core.ids import new_id
from searcher.core.time import utc_now
from searcher.index.keys import cache_key, versions_from_settings, with_parameters
from searcher.index.liveness import apply_liveness_ttl, present_availability
from searcher.index.sanitize import listing_content_digest
from searcher.index.store import WarmIndex, hypothesis_digest
from searcher.index.text import field_terms
from searcher.storage.repositories import Repositories


def _candidate(
    *,
    url: str = "https://fixture.local/listings/gat-1",
    title: str = "Dior Homme General Army Trainer 07",
    checked=None,
    availability: Availability = Availability.LIVE,
) -> ListingCandidate:
    now = checked or utc_now()
    return ListingCandidate(
        candidate_id=new_id(),
        canonical_url=url,
        source_adapter="fixture.dior_minimal",
        source_listing_id="gat-1",
        title=ClassifiedFact(
            value=title, fact_class=FactClass.REPORTED_BY_SELLER, origin=FactOrigin.SELLER
        ),
        description=ClassifiedFact(
            value="Black olive GAT lateral heel",
            fact_class=FactClass.REPORTED_BY_SELLER,
            origin=FactOrigin.SELLER,
        ),
        availability=availability,
        first_seen_at=now,
        last_checked_at=now,
    )


def test_put_get_roundtrip(db: object) -> None:
    repos = Repositories(db)  # type: ignore[arg-type]
    index = WarmIndex(repos)
    versions = versions_from_settings()
    candidate = _candidate()
    digest = listing_content_digest(candidate)
    key = index.put_listing(candidate, versions)
    assert key == cache_key(content_digest=digest, versions=versions)
    loaded = index.get(content_digest=digest, versions=versions)
    assert loaded is not None
    assert loaded["canonical_url"] == candidate.canonical_url
    assert loaded["last_checked_at"]
    hits = index.search(field_terms("Dior Homme General Army Trainer"), versions)
    assert len(hits) == 1
    assert hits[0].canonical_url == candidate.canonical_url


@pytest.mark.parametrize(
    "field",
    [
        "adapter_version",
        "model_version",
        "parameters",
        "schema_version",
        "policy_version",
    ],
)
def test_cache_key_invalidates_on_each_version_component(db: object, field: str) -> None:
    repos = Repositories(db)  # type: ignore[arg-type]
    index = WarmIndex(repos)
    versions = versions_from_settings()
    candidate = _candidate()
    digest = listing_content_digest(candidate)
    index.put_listing(candidate, versions)
    changed = with_parameters(versions, versions.parameters)
    if field == "parameters":
        changed = with_parameters(versions, "other-params")
    else:
        kwargs = {
            "adapter_version": versions.adapter_version,
            "model_version": versions.model_version,
            "parameters": versions.parameters,
            "schema_version": versions.schema_version,
            "policy_version": versions.policy_version,
        }
        kwargs[field] = kwargs[field] + "-changed"
        from searcher.index.keys import CacheVersions

        changed = CacheVersions(**kwargs)
    assert index.get(content_digest=digest, versions=changed) is None
    assert index.get(content_digest=digest, versions=versions) is not None
    hits = index.search(field_terms("dior homme trainer"), changed)
    assert hits == []


def test_expired_liveness_is_unverified_never_live(db: object) -> None:
    repos = Repositories(db)  # type: ignore[arg-type]
    index = WarmIndex(repos)
    versions = versions_from_settings()
    old = utc_now() - timedelta(hours=10)
    candidate = _candidate(checked=old)
    index.put_listing(candidate, versions)
    loaded = index.get_by_url(candidate.canonical_url, versions)
    assert loaded is not None
    stored = ListingCandidate.model_validate(loaded["payload"])
    presented = apply_liveness_ttl(stored, ttl_seconds=3600)
    assert presented.last_checked_at == stored.last_checked_at
    assert presented.availability is Availability.UNKNOWN
    assert present_availability(Availability.LIVE, old, ttl_seconds=3600) is Availability.UNKNOWN
    assert presented.explanation.last_checked_at == stored.last_checked_at
    assert presented.explanation.live_status is Availability.UNKNOWN


def test_cross_campaign_isolation(db: object, store: object) -> None:
    repos = Repositories(db)  # type: ignore[arg-type]
    index = WarmIndex(repos)
    versions = versions_from_settings()
    listing = _candidate()
    index.put_listing(listing, versions)
    store.put_private("campaign-a", "reference.png", b"private-bytes")  # type: ignore[attr-defined]
    with pytest.raises(CrossCampaignAccessError):
        index.put_private("campaign-a", "reference.png", b"private-bytes")
    with pytest.raises(CrossCampaignAccessError):
        index.campaign_private_artifacts("campaign-a")
    private = _candidate(url="https://fixture.local/private")
    private.seller_metadata["local_path"] = "/home/someone/secret.png"
    # seller_metadata is stripped; a raw private path in title must refuse.
    hostile = _candidate(title="see /home/someone/secret.png")
    with pytest.raises(CrossCampaignAccessError):
        index.put_listing(hostile, versions)
    hits = index.search(field_terms("dior homme general army"), versions)
    blob = str(hits[0].payload)
    assert "reference.png" not in blob
    assert "private-bytes" not in blob
    assert store.get_private("campaign-a", "reference.png") == b"private-bytes"  # type: ignore[attr-defined]


def test_ior_respects_versions(db: object) -> None:
    repos = Repositories(db)  # type: ignore[arg-type]
    index = WarmIndex(repos)
    versions = versions_from_settings()
    index.record_query(
        source_id="fixture.dior_minimal",
        query_text="Dior GAT 07",
        versions=versions,
    )
    assert index.query_already_run(
        source_id="fixture.dior_minimal", query_text="dior gat 07", versions=versions
    )
    from searcher.index.keys import CacheVersions

    bumped = CacheVersions(
        adapter_version=versions.adapter_version + "-x",
        model_version=versions.model_version,
        parameters="ior:fixture.dior_minimal",
        schema_version=versions.schema_version,
        policy_version=versions.policy_version,
    )
    assert not index.query_already_run(
        source_id="fixture.dior_minimal", query_text="dior gat 07", versions=bumped
    )


def test_hypothesis_digest_is_content_not_id() -> None:
    first = make_hypothesis(search_id="a")
    second = make_hypothesis(search_id="b")
    assert hypothesis_digest(first) == hypothesis_digest(second)
