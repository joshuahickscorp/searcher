"""A refused fetch is not a dead link.

The listing at the centre of this project was hidden by INACCESSIBLE_DESTINATION
because the verification fetch met a challenge, even though the URL came from
the shop's own product feed and matching had already scored it 0.61. Being
refused says something about us, not about whether the listing exists.
"""

from __future__ import annotations

from tests.helpers_matching import make_candidate

from searcher.contracts.enums import Availability
from searcher.ranking.vetoes import INACCESSIBLE, collect_hard_vetoes


def _candidate() -> object:
    candidate, _pngs = make_candidate(
        candidate_id="c1",
        url="https://shop.example/products/1",
        title="plain long sleeve cutsew",
        description="black, size L",
    )
    return candidate.model_copy(update={"availability": Availability.UNKNOWN})


def _vetoes(*, attested: bool) -> list[str]:
    return collect_hard_vetoes(
        candidate=_candidate(),
        item_hard=[],
        auth_hard=[],
        item_lower=0.61,
        destination_verified=False,
        destination_attested=attested,
        stolen_photo=False,
        duplicate_no_utility=False,
        dead_listing_is_hard_veto=False,
        plausible_floor=0.35,
        exact_colour_required=False,
    )


def test_unreachable_and_unattested_is_still_inaccessible() -> None:
    assert INACCESSIBLE in _vetoes(attested=False)


def test_a_url_the_shop_published_itself_is_not_inaccessible() -> None:
    assert INACCESSIBLE not in _vetoes(attested=True)


def test_feed_provenance_is_read_from_the_structured_dict() -> None:
    """structured_data is a dict on the model, not an object.

    Reading it with getattr answered False for every candidate, so the attested
    flag never reached the veto and the fix looked like it had not worked.
    """
    from searcher.campaigns.orchestrator import _from_index_feed

    class _Candidate:
        structured_data = {"raw": {"from_index_feed": True}}

    class _NoFeed:
        structured_data = {"raw": {"from_index_feed": False}}

    class _NoRaw:
        structured_data: dict[str, object] = {}

    assert _from_index_feed(_Candidate()) is True
    assert _from_index_feed(_NoFeed()) is False
    assert _from_index_feed(_NoRaw()) is False
