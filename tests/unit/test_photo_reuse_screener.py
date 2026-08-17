"""The screener the Real gate has been waiting for.

`IMAGE_THEFT_OR_SCAM` fired only on a flag production never set, so a listing
built from the brand's own photographs published as Real with no veto. This
screens for it from data already in the candidate set: an image appearing under
two different sellers was taken by at most one of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from searcher.authenticity.photo_reuse import screen_photo_reuse


@dataclass
class _Image:
    duplicate_family_id: str | None = None
    perceptual_hash: str | None = None
    content_digest: str | None = None


@dataclass
class _Candidate:
    candidate_id: str
    source_adapter: str = "shop"
    seller_metadata: dict[str, str] = field(default_factory=dict)
    images: list[_Image] = field(default_factory=list)


def _c(cid: str, seller: str, *families: str, source: str = "shop") -> _Candidate:
    return _Candidate(
        candidate_id=cid,
        source_adapter=source,
        seller_metadata={"seller_id": seller},
        images=[_Image(duplicate_family_id=f) for f in families],
    )


def test_an_image_under_two_sellers_is_reuse() -> None:
    reused, stock = screen_photo_reuse([_c("a", "alice", "img1"), _c("b", "bob", "img1")])
    assert reused == {"a", "b"}, "both carry a photograph only one of them took"
    assert stock == set(), "two sellers is reuse, not catalogue imagery"


def test_one_seller_reusing_their_own_photograph_is_ordinary() -> None:
    reused, stock = screen_photo_reuse([_c("a", "alice", "img1"), _c("b", "alice", "img1")])
    assert reused == set(), "a seller may photograph once and list twice"
    assert stock == set()


def test_an_image_under_many_sellers_is_stock() -> None:
    rows = [_c(str(i), f"seller{i}", "official") for i in range(4)]
    reused, stock = screen_photo_reuse(rows)
    assert stock == {"0", "1", "2", "3"}
    assert stock <= reused, "stock imagery is also reuse; the labels are not exclusive"


def test_distinct_photographs_are_clean() -> None:
    reused, stock = screen_photo_reuse([_c("a", "alice", "x"), _c("b", "bob", "y")])
    assert (reused, stock) == (set(), set())


def test_screening_an_empty_set_still_counts_as_screening() -> None:
    """Empty means nothing found. The gate distinguishes that from nobody looking."""
    reused, stock = screen_photo_reuse([])
    assert reused == set() and stock == set()


def test_a_missing_seller_falls_back_to_the_source_conservatively() -> None:
    """Unknown sellers must under-report reuse rather than invent it."""
    a = _Candidate(candidate_id="a", source_adapter="shop", images=[_Image("img1")])
    b = _Candidate(candidate_id="b", source_adapter="shop", images=[_Image("img1")])
    reused, _ = screen_photo_reuse([a, b])
    assert reused == set(), "same source and no seller recorded is treated as one seller"

    c = _Candidate(candidate_id="c", source_adapter="other", images=[_Image("img1")])
    reused, _ = screen_photo_reuse([a, c])
    assert reused == {"a", "c"}, "different sources are different sellers"


def test_a_perceptual_hash_identifies_an_image_when_no_family_is_set() -> None:
    a = _Candidate(candidate_id="a", seller_metadata={"seller_id": "alice"},
                   images=[_Image(perceptual_hash="ph1")])
    b = _Candidate(candidate_id="b", seller_metadata={"seller_id": "bob"},
                   images=[_Image(perceptual_hash="ph1")])
    reused, _ = screen_photo_reuse([a, b])
    assert reused == {"a", "b"}
