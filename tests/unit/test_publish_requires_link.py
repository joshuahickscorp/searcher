"""A published result must be openable.

An independent adversarial pass published a Possibly Real card with
listing_url null and no reason codes, and another whose canonical_url was a
javascript: URL. Both rendered as results a reader could not open. The product
is "here is where to find this"; a card that goes nowhere is worse than no card.
"""

from __future__ import annotations

import pytest
from tests.helpers_matching import make_candidate

from searcher.campaigns.publication import has_usable_listing_link, published_public_bucket
from searcher.contracts.enums import BucketPublic


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
        assert published_public_bucket(_Decision(bucket), _candidate(url)) == (
            BucketPublic.HIDDEN.value
        )


def test_an_ordinary_listing_still_publishes() -> None:
    candidate = _candidate("https://shop.kind.co.jp/products/8001001141404")
    assert has_usable_listing_link(candidate) is True
    decision = _Decision(BucketPublic.POSSIBLY_REAL)
    decision.reason_codes = ["possibly-real-gate"]
    assert published_public_bucket(decision, candidate) == BucketPublic.POSSIBLY_REAL.value


def test_a_missing_candidate_cannot_be_published() -> None:
    assert published_public_bucket(_Decision(BucketPublic.REAL), None) == BucketPublic.HIDDEN.value


def test_a_result_without_reason_codes_is_not_published() -> None:
    """Round 3: a row with a valid https URL and no reason codes still published.

    Every published result states why it is where it is. A row that cannot is a
    claim nobody can interrogate, so it stays hidden and counted.
    """
    candidate = _candidate("https://shop.kind.co.jp/products/8001001141404")
    decision = _Decision(BucketPublic.POSSIBLY_REAL)
    assert decision.reason_codes == []
    assert published_public_bucket(decision, candidate) == BucketPublic.HIDDEN.value

    decision.reason_codes = ["possibly-real-gate"]
    assert published_public_bucket(decision, candidate) == (
        BucketPublic.POSSIBLY_REAL.value
    )
