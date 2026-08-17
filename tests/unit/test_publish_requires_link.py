"""A published result must be openable.

An independent adversarial pass published a Possibly Real card with
listing_url null and no reason codes, and another whose canonical_url was a
javascript: URL. Both rendered as results a reader could not open. The product
is "here is where to find this"; a card that goes nowhere is worse than no card.
"""

from __future__ import annotations

import pytest

from searcher.campaigns.publication import has_usable_listing_link, published_public_bucket
from searcher.contracts.enums import BucketPublic
from tests.helpers_matching import make_candidate


def _candidate(url: str):
    candidate, _pngs = make_candidate(
        candidate_id="c1",
        url="https://shop.example/products/1",
        title="plain long sleeve cutsew",
        description="black",
    )
    return candidate.model_copy(update={"canonical_url": url})


class _Decision:
    def __init__(self, public: BucketPublic) -> None:
        self.decision = type("D", (), {"public": public})()
        self.hard_vetoes: list[str] = []
        self.reason_codes: list[str] = []


@pytest.mark.parametrize("url", ["", "javascript:alert(1)", "data:text/html,x", "/products/1"])
def test_a_candidate_without_a_usable_link_is_not_published(url: str) -> None:
    assert has_usable_listing_link(_candidate(url)) is False
    for bucket in (BucketPublic.REAL, BucketPublic.POSSIBLY_REAL):
        assert published_public_bucket(_Decision(bucket), _candidate(url)) == BucketPublic.HIDDEN.value


def test_an_ordinary_listing_still_publishes() -> None:
    candidate = _candidate("https://shop.kind.co.jp/products/8001001141404")
    assert has_usable_listing_link(candidate) is True
    assert published_public_bucket(_Decision(BucketPublic.POSSIBLY_REAL), candidate) == (
        BucketPublic.POSSIBLY_REAL.value
    )


def test_a_missing_candidate_cannot_be_published() -> None:
    assert published_public_bucket(_Decision(BucketPublic.REAL), None) == BucketPublic.HIDDEN.value
