"""Expected information gain. Later rounds run only when gain justifies them."""

from __future__ import annotations

from searcher.contracts.models import QueryVariant

ROUND_GAIN_FLOOR = {
    0: 0.0,
    1: 0.04,
    2: 0.06,
    3: 0.08,
    4: 0.10,
    5: 0.12,
}


def score_gain(
    *,
    posterior: float,
    novelty: float,
    overlap: float,
    new_sources: int,
    cost: float,
) -> float:
    coverage = min(1.0, 0.25 * new_sources)
    raw = posterior * novelty * (1.0 - overlap) * (0.4 + coverage)
    return round(max(0.0, raw / (1.0 + cost)), 4)


def order_by_gain(queries: list[QueryVariant]) -> list[QueryVariant]:
    return sorted(queries, key=lambda q: (-q.expected_gain, q.cost_estimate, q.query_text))


def round_justified(round_no: int, queries: list[QueryVariant]) -> bool:
    floor = ROUND_GAIN_FLOOR.get(round_no, 0.12)
    if round_no == 0:
        return True
    return any(q.round == round_no and q.expected_gain >= floor for q in queries)
