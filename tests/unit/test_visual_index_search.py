"""Retrieval must be able to find a listing its text cannot name.

The index stored image descriptors and nothing ever searched them, so retrieval
was text-only. A listing whose title carries no brand, model or year could not
be found by any compiled query, and image matching never saw it, because
matching only runs on candidates text retrieval already returned.

That is why photographs of KIND listing 8001001141404 return nothing: its title
is a plain garment noun and it sits past 2000 items in the catalogue feed. No
amount of ranking work reaches it. Searching the descriptors does.
"""

from __future__ import annotations

import array
import math

import pytest

from searcher.storage.connection import Database
from searcher.storage.index_tables import IndexTables
from searcher.storage.migrations import migrate


def _blob(values: list[float]) -> bytes:
    return array.array("f", values).tobytes()


@pytest.fixture
def index(tmp_path) -> IndexTables:  # type: ignore[no-untyped-def]
    db = Database(tmp_path / "index.db")
    migrate(db)
    return IndexTables(db)


def _listing(index: IndexTables, key: str) -> None:
    """Descriptors hang off a listing row, so one has to exist first."""
    index.upsert_listing(
        {
            "listing_key": key,
            "canonical_url": f"https://example.test/{key}",
            "content_digest": f"{key}-content",
            "adapter_version": "1",
            "model_version": "1",
            "parameters": "{}",
            "schema_version": "1.1.0",
            "policy_version": "matching-1",
            "source_adapter": "shop",
            "source_listing_id": key,
            "cluster_key": key,
            "availability": "LIVE",
            "last_checked_at": "2026-08-17T00:00:00Z",
            "first_seen_at": "2026-08-17T00:00:00Z",
            "title_norm": "",
            "description_norm": "",
            "ocr_terms": "",
            "image_digests": [],
            "perceptual_hashes": [],
            "payload": {},
        }
    )


def _add(index: IndexTables, key: str, values: list[float], kind: str = "image") -> None:
    _listing(index, key)
    index.replace_descriptors(key, [(f"{key}-digest", len(values), _blob(values), kind)])


def test_the_nearest_descriptor_ranks_first(index: IndexTables) -> None:
    _add(index, "target", [1.0, 0.0, 0.0])
    _add(index, "other", [0.0, 1.0, 0.0])
    ranked = index.search_listings_by_descriptor([1.0, 0.0, 0.0], kind="image")
    assert ranked and ranked[0][0] == "target"
    assert ranked[0][1] == pytest.approx(1.0)


def test_a_listing_with_no_matching_text_is_still_findable(index: IndexTables) -> None:
    """The known-item scenario, reduced to its mechanism."""
    _add(index, "plain-garment", [0.9, 0.1, 0.0])
    for i in range(20):
        _add(index, f"noise{i}", [0.0, 0.0, 1.0])
    ranked = index.search_listings_by_descriptor([1.0, 0.0, 0.0], kind="image")
    assert ranked[0][0] == "plain-garment", "the item text cannot name was not retrieved"


def test_descriptors_of_another_dimension_are_skipped_not_truncated(
    index: IndexTables,
) -> None:
    """Comparing across model versions is meaningless; answering anyway is worse."""
    _add(index, "wrong-dim", [1.0, 0.0])
    _add(index, "right-dim", [0.5, 0.5, 0.5])
    ranked = index.search_listings_by_descriptor([1.0, 0.0, 0.0], kind="image")
    assert [key for key, _ in ranked] == ["right-dim"]


def test_kind_separates_descriptor_families(index: IndexTables) -> None:
    _add(index, "global-one", [1.0, 0.0, 0.0], kind="image")
    _add(index, "parts-one", [1.0, 0.0, 0.0], kind="parts")
    ranked = index.search_listings_by_descriptor([1.0, 0.0, 0.0], kind="parts")
    assert [key for key, _ in ranked] == ["parts-one"]


def test_a_zero_or_empty_query_returns_nothing_rather_than_everything(
    index: IndexTables,
) -> None:
    _add(index, "target", [1.0, 0.0, 0.0])
    assert index.search_listings_by_descriptor([], kind="image") == []
    assert index.search_listings_by_descriptor([0.0, 0.0, 0.0], kind="image") == []


def test_min_similarity_excludes_distant_listings(index: IndexTables) -> None:
    _add(index, "near", [1.0, 0.05, 0.0])
    _add(index, "far", [0.0, 0.0, 1.0])
    ranked = index.search_listings_by_descriptor(
        [1.0, 0.0, 0.0], kind="image", min_similarity=0.5
    )
    assert [key for key, _ in ranked] == ["near"]


def test_the_best_image_represents_a_multi_image_listing(index: IndexTables) -> None:
    """A listing is as close as its closest photograph, not its average one."""
    _listing(index, "multi")
    index.replace_descriptors(
        "multi",
        [
            ("a", 3, _blob([0.0, 0.0, 1.0]), "image"),
            ("b", 3, _blob([1.0, 0.0, 0.0]), "image"),
        ],
    )
    ranked = index.search_listings_by_descriptor([1.0, 0.0, 0.0], kind="image")
    assert ranked[0][0] == "multi"
    assert ranked[0][1] == pytest.approx(1.0), "the matching photograph should decide"
    assert math.isfinite(ranked[0][1])


def test_a_descriptor_retrieves_a_listing_text_never_returned(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The wiring, not just the capability.

    `IndexStore.search` accepted a query descriptor before this and used it only
    to rescore rows the text search had already returned - the descriptor map
    was built from those keys. A listing whose title matches no term stayed
    invisible however close its photographs were. Visual evidence must be able
    to put a listing into the candidate set, not only reorder one already there.
    """
    from searcher.index.keys import CacheVersions
    from searcher.index.store import WarmIndex

    db = Database(tmp_path / "index.db")
    migrate(db)
    index = IndexTables(db)

    class _Repos:
        def __init__(self, tables: IndexTables) -> None:
            self.index = tables

    store = WarmIndex(_Repos(index))  # type: ignore[arg-type]

    _add(index, "plain-garment", [1.0, 0.0, 0.0])
    index.replace_terms("plain-garment", [])

    versions = CacheVersions(
        adapter_version="1",
        model_version="1",
        parameters="{}",
        schema_version="1.1.0",
        policy_version="matching-1",
    )

    text_only = store.search(["archive", "trainer"], versions)
    assert not text_only, "precondition: no term names this listing"

    with_vision = store.search(["archive", "trainer"], versions, query_descriptor=[1.0, 0.0, 0.0])
    assert [hit.listing_key for hit in with_vision] == ["plain-garment"], (
        "a listing no term names must still be retrievable by its photographs"
    )


def test_the_consult_path_prefers_an_image_descriptor_over_a_text_vector() -> None:
    """The consult path must address the image space with an image.

    `search_listings_by_descriptor` works and `WarmIndex.search` merges its
    results. But the only production caller, `consult_and_surface`, passes
    `hashed_text_vector(terms)` - a 64-dimension vector derived from words -
    while stored image descriptors are 384-dimension. The dimension guard skips
    the mismatch, so the descriptor search returns nothing on that path.

    `consult_and_surface` passed `hashed_text_vector(terms)`, a 64-dimension
    vector derived from words, while every stored descriptor is a 384-dimension
    image embedding. The dimension guard skipped the mismatch, so the descriptor
    search returned nothing and the rescoring of text hits scored nothing: the
    visual half of consulting the index never ran.

    The guard is why that was inert rather than harmful - comparing a text
    vector against image descriptors yields a meaningless cosine and would
    retrieve listings for no reason. The fix is to send an image.
    """
    import inspect

    from searcher.core.embedding_gateway import FEATURE_DIM
    from searcher.index import consult
    from searcher.index.consult import hashed_text_vector

    source = inspect.getsource(consult.consult_and_surface)
    assert "_reference_descriptor(controller, search_id)" in source, (
        "the query descriptor must come from the user's photographs"
    )

    # The text vector remains only as a fallback, and it still cannot address
    # the image space. If these dimensions ever coincide it would silently start
    # being compared against image descriptors.
    assert len(hashed_text_vector(["archive", "trainer"])) != FEATURE_DIM
