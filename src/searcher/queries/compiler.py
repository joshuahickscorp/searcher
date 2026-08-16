"""Query compiler entry point."""

from __future__ import annotations

from searcher.contracts.models import ItemHypothesis, QueryVariant, ReferenceAnalysis
from searcher.queries.planner import DEFAULT_CEILING, compile_plan


def compile_queries(
    hypotheses: list[ItemHypothesis],
    analysis: ReferenceAnalysis | None = None,
    *,
    ceiling: int = DEFAULT_CEILING,
    demoted: set[str] | None = None,
    prior: list[QueryVariant] | None = None,
) -> list[QueryVariant]:
    visual_terms: list[str] = []
    codes: list[str] = []
    if analysis is not None:
        visual_terms = [
            rel.split()[0] for rel in analysis.visual_signature.distinctive_relations if rel.split()
        ]
        codes = [
            obs.text
            for obs in analysis.text_and_marks
            if obs.kind == "product_code" and not obs.injection_candidate
        ]
    return compile_plan(
        hypotheses,
        ceiling=ceiling,
        demoted=demoted,
        prior=prior,
        visual_terms=visual_terms,
        product_codes=codes,
    )
