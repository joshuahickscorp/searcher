"""Query compiler entry point."""

from __future__ import annotations

from searcher.contracts.enums import QueryStatus, QueryType
from searcher.contracts.models import ItemHypothesis, QueryVariant, ReferenceAnalysis
from searcher.core.ids import new_id
from searcher.queries.planner import DEFAULT_CEILING, compile_plan


def compile_queries(
    hypotheses: list[ItemHypothesis],
    analysis: ReferenceAnalysis | None = None,
    *,
    ceiling: int = DEFAULT_CEILING,
    demoted: set[str] | None = None,
    prior: list[QueryVariant] | None = None,
    product_codes: list[str] | None = None,
    user_terms: list[str] | None = None,
) -> list[QueryVariant]:
    visual_terms: list[str] = []
    codes: list[str] = list(product_codes or [])
    if analysis is not None:
        visual_terms = [
            rel.split()[0] for rel in analysis.visual_signature.distinctive_relations if rel.split()
        ]
        codes.extend(
            obs.text
            for obs in analysis.text_and_marks
            if obs.kind == "product_code" and not obs.injection_candidate
        )
    variants = compile_plan(
        hypotheses,
        ceiling=ceiling,
        demoted=demoted,
        prior=prior,
        visual_terms=visual_terms,
        product_codes=codes,
    )
    if variants:
        return variants
    fallback = " ".join(part.strip() for part in (user_terms or []) if part and part.strip())
    if not fallback:
        return variants
    hid = hypotheses[0].hypothesis_id if hypotheses else ""
    variants.append(
        QueryVariant(
            query_id=new_id(),
            hypothesis_id=hid,
            round=0,
            language="en",
            query_text=fallback,
            query_type=QueryType.EXACT_NAME,
            status=QueryStatus.QUEUED,
            expected_gain=0.4,
            cost_estimate=0.1,
            family="user_fallback",
        )
    )
    return variants
