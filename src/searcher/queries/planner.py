"""Round planner. Later rounds run only when expected gain justifies them."""

from __future__ import annotations

from searcher.contracts.enums import QueryStatus
from searcher.contracts.models import ItemHypothesis, QueryVariant
from searcher.core.ids import new_id
from searcher.queries.dedupe import dedupe_queries, drop_demoted, jaccard
from searcher.queries.families import drafts_for_hypothesis
from searcher.queries.information_gain import ROUND_GAIN_FLOOR, order_by_gain, score_gain

MAX_PER_FAMILY = 8
MAX_PER_ROUND = 16
DEFAULT_CEILING = 48


def compile_plan(
    hypotheses: list[ItemHypothesis],
    *,
    ceiling: int = DEFAULT_CEILING,
    demoted: set[str] | None = None,
    prior: list[QueryVariant] | None = None,
    visual_terms: list[str] | None = None,
    product_codes: list[str] | None = None,
) -> list[QueryVariant]:
    demoted = set(demoted or set())
    drafts = []
    for hyp in hypotheses:
        if hyp.posterior <= 0:
            continue
        drafts.extend(
            drafts_for_hypothesis(
                hyp, demoted=demoted, visual_terms=visual_terms, product_codes=product_codes
            )
        )
    variants: list[QueryVariant] = []
    prior_texts = [q.query_text for q in (prior or [])]
    for draft in drafts:
        overlap = 0.0
        if prior_texts:
            overlap = max(jaccard(draft.text, prev) for prev in prior_texts)
        matched = next((h for h in hypotheses if h.hypothesis_id in draft.origin), None)
        posterior = matched.posterior if matched is not None else 0.2
        gain = score_gain(
            posterior=posterior,
            novelty=draft.novelty,
            overlap=overlap,
            new_sources=len(draft.sources),
            cost=draft.cost,
        )
        record: dict[str, object] | None = None
        if draft.translation is not None:
            record = {
                "source_term": draft.translation.source_term,
                "translated_term": draft.translation.translated_term,
                "language": draft.translation.language,
                "tool": draft.translation.tool,
                "confidence": draft.translation.confidence,
                "improved_verified_retrieval": draft.translation.improved_verified_retrieval,
            }
        variants.append(
            QueryVariant(
                query_id=new_id(),
                hypothesis_id=draft.origin[0] if draft.origin else "",
                round=draft.round,
                language=draft.language,
                query_text=draft.text,
                query_type=draft.query_type,
                origin_evidence=list(draft.origin),
                expected_gain=gain,
                cost_estimate=draft.cost,
                status=QueryStatus.QUEUED,
                source_coverage=list(draft.sources),
                overlap=round(overlap, 4),
                family=draft.family,
                provisional=draft.provisional,
                translation_record=record,
            )
        )
    variants = drop_demoted(variants, demoted)
    variants = dedupe_queries(order_by_gain(variants))

    selected: list[QueryVariant] = []
    family_counts: dict[str, int] = {}
    round_counts: dict[int, int] = {}
    enabled_rounds = {0}
    for round_no in range(1, 6):
        floor = ROUND_GAIN_FLOOR[round_no]
        in_round = [query for query in variants if query.round == round_no]
        if not in_round:
            continue
        if any(query.expected_gain >= floor for query in in_round):
            enabled_rounds.add(round_no)
        else:
            break
    for query in variants:
        if query.round not in enabled_rounds:
            continue
        family_counts[query.family] = family_counts.get(query.family, 0) + 1
        round_counts[query.round] = round_counts.get(query.round, 0) + 1
        if family_counts[query.family] > MAX_PER_FAMILY:
            continue
        if round_counts[query.round] > MAX_PER_ROUND:
            continue
        selected.append(query)
        if len(selected) >= ceiling:
            break

    def _counts() -> dict[str, int]:
        tally: dict[str, int] = {}
        for item in selected:
            tally[item.language] = tally.get(item.language, 0) + 1
        return tally

    have = set(_counts())
    for query in variants:
        if query.language in have or query.round not in enabled_rounds:
            continue
        if len(selected) < ceiling:
            selected.append(query)
            have.add(query.language)
            continue
        counts = _counts()
        extras = [item for item in selected if counts.get(item.language, 0) > 1]
        if not extras:
            break
        extra = min(extras, key=lambda item: item.expected_gain)
        selected.remove(extra)
        selected.append(query)
        have.add(query.language)
    return selected
