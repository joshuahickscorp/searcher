"""Query dedupe, information-gain order, language routing."""

from __future__ import annotations

from searcher.contracts.enums import FactClass, FactOrigin, QueryType
from searcher.contracts.models import ItemHypothesis, QueryVariant, VisualSignature
from searcher.core.ids import new_id
from searcher.hypotheses.beliefs import make_belief
from searcher.queries.compiler import compile_queries
from searcher.queries.dedupe import dedupe_queries, drop_demoted, normalize_query_text
from searcher.queries.information_gain import order_by_gain, score_gain
from searcher.queries.languages import ADMITTED_SOURCES, sources_for, transliterate_brand


def _b(value: str | None, cls: FactClass, origin: FactOrigin, conf: float) -> object:
    return make_belief(value, confidence=conf, fact_class=cls, origin=origin)


def _hyp() -> ItemHypothesis:
    empty = _b(None, FactClass.UNRESOLVED, FactOrigin.SYSTEM, 0.0)
    return ItemHypothesis(
        hypothesis_id=new_id(),
        search_id="s",
        category="footwear",
        brand=_b("House Name", FactClass.USER_SUPPLIED, FactOrigin.USER, 0.6),
        model_name=_b("Field Model", FactClass.USER_SUPPLIED, FactOrigin.USER, 0.5),
        line=empty,
        designer=empty,
        season=empty,
        year=_b("2007", FactClass.USER_SUPPLIED, FactOrigin.USER, 0.4),
        colourway=_b("black", FactClass.USER_SUPPLIED, FactOrigin.USER, 0.3),
        visual_signature=VisualSignature(),
        posterior=0.5,
    )


def test_dedupe_collapses_cosmetic_variants() -> None:
    a = QueryVariant(
        query_id="1",
        hypothesis_id="h",
        round=0,
        language="en",
        query_text="House Name Field Model",
        query_type=QueryType.EXACT_NAME,
        expected_gain=0.4,
    )
    b = QueryVariant(
        query_id="2",
        hypothesis_id="h",
        round=0,
        language="en",
        query_text="  house  name   field model ",
        query_type=QueryType.EXACT_NAME,
        expected_gain=0.3,
    )
    assert len(dedupe_queries([a, b])) == 1


def test_information_gain_orders_higher_first() -> None:
    low = QueryVariant(
        query_id="1",
        hypothesis_id="h",
        round=2,
        language="en",
        query_text="a",
        query_type=QueryType.TRANSLATED,
        expected_gain=0.1,
        cost_estimate=0.4,
    )
    high = QueryVariant(
        query_id="2",
        hypothesis_id="h",
        round=0,
        language="en",
        query_text="b",
        query_type=QueryType.EXACT_NAME,
        expected_gain=0.8,
        cost_estimate=0.1,
    )
    ordered = order_by_gain([low, high])
    assert ordered[0].query_id == "2"
    high_gain = score_gain(posterior=0.5, novelty=1.0, overlap=0.0, new_sources=2, cost=0.1)
    low_gain = score_gain(posterior=0.5, novelty=0.2, overlap=0.9, new_sources=1, cost=0.4)
    assert high_gain > low_gain


def test_language_routing_only_admitted_sources() -> None:
    for lang, sources in ADMITTED_SOURCES.items():
        assert sources_for(lang) == sources
        assert sources
    assert "grailed" not in sources_for("en")
    assert "komehyo" in sources_for("ja")
    assert "wikipedia_ko" in sources_for("ko")


def test_compiler_is_multilingual_and_bounded() -> None:
    queries = compile_queries([_hyp()], ceiling=48)
    langs = {q.language for q in queries}
    assert {"en", "ja", "ko", "zh", "fr", "it", "ru"} <= langs
    assert len(queries) <= 48
    types = {q.query_type for q in queries}
    assert QueryType.EXACT_NAME in types
    assert QueryType.TRANSLATED in types
    assert QueryType.NEGATIVE_RESEARCH in types
    # Brand preserved verbatim in at least one non-English query.
    assert any(q.language != "en" and "House Name" in q.query_text for q in queries)
    # Translations recorded, original not overwritten.
    translated = [q for q in queries if q.translation_record]
    assert translated
    rec = translated[0].translation_record
    assert rec is not None
    assert "source_term" in rec
    assert rec.get("improved_verified_retrieval") is False


def test_demoted_term_stops_generating() -> None:
    queries = compile_queries([_hyp()], demoted={"replica"})
    assert all("replica" not in q.query_text.lower() for q in queries)
    leftover = drop_demoted(queries, {"field"})
    assert all("field" not in normalize_query_text(q.query_text) for q in leftover)


def test_transliteration_is_algorithmic_not_item_specific() -> None:
    ja = transliterate_brand("House Name", "ja")
    assert ja
    assert "House" not in ja
    # Must not contain a hardcoded flagship rendering.
    assert "ディオール" not in ja
