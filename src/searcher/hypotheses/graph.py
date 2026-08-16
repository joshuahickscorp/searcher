"""ProductHypothesisGraph. Searcher-owned; not the donor world model."""

from __future__ import annotations

from searcher.contracts.enums import HypothesisStatus
from searcher.contracts.models import ItemHypothesis
from searcher.contracts.primitives import SearcherModel
from searcher.core.ids import new_id


class HypothesisEdge(SearcherModel):
    source: str
    target: str
    relation: str
    note: str = ""


class ProductHypothesisGraph(SearcherModel):
    graph_id: str
    search_id: str
    nodes: list[str]
    edges: list[HypothesisEdge]
    archived: list[str]


def build_graph(search_id: str, hypotheses: list[ItemHypothesis]) -> ProductHypothesisGraph:
    edges: list[HypothesisEdge] = []
    ids = [h.hypothesis_id for h in hypotheses]
    active = [h for h in hypotheses if h.status is HypothesisStatus.ACTIVE]
    for i, left in enumerate(active):
        for right in active[i + 1 :]:
            relation = "competes"
            if left.brand.value and right.brand.value and left.brand.value != right.brand.value:
                relation = "contradicts_brand"
            elif left.year.value and right.year.value and left.year.value != right.year.value:
                relation = "adjacent_year"
            elif left.model_name.value == right.model_name.value:
                relation = "same_model_reading"
            edges.append(
                HypothesisEdge(
                    source=left.hypothesis_id,
                    target=right.hypothesis_id,
                    relation=relation,
                )
            )
    return ProductHypothesisGraph(
        graph_id=new_id(),
        search_id=search_id,
        nodes=ids,
        edges=edges,
        archived=[h.hypothesis_id for h in hypotheses if h.status is HypothesisStatus.ARCHIVED],
    )
