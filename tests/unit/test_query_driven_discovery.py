"""Source adapters must query the source, not crawl an unrelated collection."""

from __future__ import annotations

from searcher.campaigns.orchestrator import FINE_COMPARE_CAP, select_kept_ids
from searcher.contracts.enums import QueryType
from searcher.contracts.models import QueryVariant
from searcher.sources.adapters.kind import KindAdapter
from searcher.sources.adapters.product import query_slugs, usable_query_text


def _query(text: str) -> QueryVariant:
    return QueryVariant(
        query_id="q",
        hypothesis_id="h",
        round=0,
        language="en",
        query_text=text,
        query_type=QueryType.EXACT_NAME,
    )


def test_usable_query_and_slugs() -> None:
    assert usable_query_text('  "Willy Chavarria"  ') == "Willy Chavarria"
    assert usable_query_text("?") == ""
    assert query_slugs("Willy Chavarria")[0] == "willy-chavarria"
    assert "dior-homme" in query_slugs("Dior Homme Army Trainer")


def test_kind_discover_is_query_driven() -> None:
    page = KindAdapter().discover(_query("Willy Chavarria"), None)
    blob = " ".join(page.urls).lower()
    assert page.urls
    assert "willy" in blob
    assert "chavarria" in blob
    assert "dior-homme" not in blob
    assert "/search" not in blob
    assert "products.json" in blob
    assert page.note == "query"


def test_kind_does_not_emit_robots_disallowed_search() -> None:
    page = KindAdapter().discover(_query("Willy Chavarria black long sleeve"), None)
    for url in page.urls:
        assert "/search" not in url
        assert "shop.kind.co.jp" in url


def test_kind_empty_query_falls_back_without_unrelated_brand() -> None:
    page = KindAdapter().discover(_query("   "), None)
    blob = " ".join(page.urls).lower()
    assert "dior-homme" not in blob
    assert page.note == "fallback"


def test_fine_compare_cap_keeps_highest_recall_first() -> None:
    ranked = [f"hit-{i}" for i in range(42)]
    filler = [f"other-{i}" for i in range(42)]
    kept = select_kept_ids(ranked, filler)
    assert kept == ranked[:FINE_COMPARE_CAP]
    assert len(kept) == 8
    assert "hit-0" in kept
    assert "other-0" not in kept


def test_kind_nonempty_query_does_not_crawl_all_collection() -> None:
    page = KindAdapter().discover(_query("ウィリーチャバリア"), None)
    blob = " ".join(page.urls).lower()
    assert "/collections/all" not in blob or "q=" in blob
    assert "dior-homme" not in blob
