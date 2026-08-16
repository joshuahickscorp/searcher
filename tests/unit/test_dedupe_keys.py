"""Dedupe key derivation."""

from __future__ import annotations

from searcher.contracts.enums import Availability, FactClass, FactOrigin, ImageRole
from searcher.contracts.models import ListingCandidate, ListingImage
from searcher.contracts.primitives import ClassifiedFact
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.deduplication.clusters import cluster_candidates
from searcher.deduplication.images import content_fingerprint
from searcher.deduplication.urls import url_cluster_key

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def _candidate(url: str, listing_id: str, digest: str) -> ListingCandidate:
    cid = new_id()
    return ListingCandidate(
        candidate_id=cid,
        canonical_url=url,
        source_adapter="kind",
        source_listing_id=listing_id,
        title=ClassifiedFact(
            value="Dior Homme", fact_class=FactClass.REPORTED_BY_SELLER, origin=FactOrigin.SELLER
        ),  # noqa: E501
        availability=Availability.LIVE,
        images=[
            ListingImage(
                listing_image_id=new_id(),
                candidate_id=cid,
                remote_url="https://img.test/" + digest,
                content_digest=digest,
                role=ImageRole.PRODUCT,
            )
        ],
        first_seen_at=_TS,
        last_checked_at=_TS,
    )


def test_same_listing_id_clusters() -> None:
    a = _candidate("https://shop.kind.co.jp/products/x?utm_source=1", "x", "a" * 64)
    b = _candidate("https://shop.kind.co.jp/products/x", "x", "b" * 64)
    assert url_cluster_key(a) == url_cluster_key(b)
    result = cluster_candidates([a, b])
    assert result.after == 1
    assert result.exact_url_dupes == 1


def test_content_fingerprint_stable() -> None:
    assert content_fingerprint(b"hello" * 20) == content_fingerprint(b"hello" * 20)
