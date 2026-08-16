"""Alias promotion, portfolio bound, query bound, demoted terms, OCR class."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from searcher.contracts.enums import FactClass, FactOrigin, HypothesisStatus
from searcher.contracts.models import (
    CategoryHypothesis,
    ItemHypothesis,
    LaneStatus,
    ReferenceAnalysis,
    TargetCluster,
    TextObservation,
    VisualSignature,
)
from searcher.core.ids import new_id
from searcher.hypotheses.aliases import (
    AliasEvidence,
    can_promote_alias,
    seller_title_alone_cannot_promote,
)
from searcher.hypotheses.beliefs import make_belief
from searcher.hypotheses.item import seed_portfolio
from searcher.hypotheses.updates import bound_portfolio
from searcher.queries.compiler import compile_queries


def _empty_analysis() -> ReferenceAnalysis:
    return ReferenceAnalysis(
        analysis_id=new_id(),
        search_id="s",
        primary_cluster=TargetCluster(cluster_id=new_id(), relation="single_view", confidence=0.4),
        category_hypotheses=[CategoryHypothesis(category="footwear", confidence=0.4)],
        lanes=[
            LaneStatus(
                name="DENSE_FEATURES",
                available=False,
                blocked=True,
                degraded=True,
                reason="blocked",
            )
        ],
        promotion_blocked=True,
    )


@given(st.text(min_size=1, max_size=24, alphabet=st.characters(whitelist_categories=("L",))))
def test_one_low_confidence_listing_cannot_promote(alias: str) -> None:
    evidence = [
        AliasEvidence(
            alias=alias,
            source_family="seller",
            authority="listing",
            confidence=0.25,
        )
    ]
    assert seller_title_alone_cannot_promote(evidence)
    assert not can_promote_alias(evidence)


@given(st.integers(min_value=1, max_value=20))
def test_hypothesis_count_stays_bounded(n: int) -> None:
    empty = make_belief(
        None, confidence=0.0, fact_class=FactClass.UNRESOLVED, origin=FactOrigin.SYSTEM
    )
    hyps = []
    for _ in range(n):
        hyps.append(
            ItemHypothesis(
                hypothesis_id=new_id(),
                search_id="s",
                status=HypothesisStatus.ACTIVE,
                category="footwear",
                brand=empty,
                model_name=empty,
                line=empty,
                designer=empty,
                season=empty,
                year=empty,
                colourway=empty,
                visual_signature=VisualSignature(),
                posterior=1.0 / max(1, n),
            )
        )
    bounded = bound_portfolio(hyps, ceiling=8)
    assert sum(1 for h in bounded if h.status is HypothesisStatus.ACTIVE) <= 8
    assert len(bounded) == n


@given(
    st.text(min_size=3, max_size=40, alphabet=st.characters(whitelist_categories=("L", "N", "Zs")))
)
def test_query_generation_is_bounded(text: str) -> None:
    hyps = seed_portfolio(
        search_id="s",
        text=text,
        tags=["black"],
        analysis=_empty_analysis(),
        ceiling=8,
    )
    queries = compile_queries(hyps, ceiling=48)
    assert len(queries) <= 48
    assert len(hyps) <= 8


@given(st.sampled_from(["replica", "w2c", "1:1", "qc pics"]))
def test_demoted_term_stops_generating(term: str) -> None:
    hyps = seed_portfolio(
        search_id="s",
        text="House Name Field Model 07",
        tags=[],
        analysis=_empty_analysis(),
        ceiling=8,
    )
    queries = compile_queries(hyps, demoted={term}, ceiling=48)
    needle = term.lower()
    assert all(needle not in q.query_text.lower() for q in queries)


@given(st.text(min_size=1, max_size=24))
def test_ocr_text_cannot_become_observed(text: str) -> None:
    with pytest.raises(ValidationError):
        TextObservation(
            text=text,
            confidence=0.8,
            fact_class=FactClass.OBSERVED,
            origin=FactOrigin.EXTRACTOR,
        )
    ok = TextObservation(
        text=text,
        confidence=0.8,
        fact_class=FactClass.EXTRACTED,
        origin=FactOrigin.EXTRACTOR,
    )
    assert ok.fact_class is FactClass.EXTRACTED
