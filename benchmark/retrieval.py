"""Closed-set retrieval: different photograph of a listing, seven degradations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .degradations import DEGRADATION_NAMES, apply_degradation
from .metrics import group_ranks, retrieval_block
from .paths import KIND_IMAGES
from .scores import Scorer, resolve_scorer
from .splits import SplitItem, SplitSet


@dataclass
class RankedCandidate:
    item_id: str
    score: float
    correct: bool
    image_name: str


@dataclass
class QueryResult:
    query_id: str
    target_id: str
    degradation: str
    query_image: str
    reference_image: str
    query_bytes: bytes
    rank: int | None
    target_score: float | None
    ranking: list[RankedCandidate]
    gallery_bytes: dict[str, bytes] = field(default_factory=dict)


@dataclass
class RetrievalReport:
    split: str
    scorer: Scorer
    protocol: str
    queries: list[QueryResult]
    wall_seconds: float
    images_scored: int
    not_computed: list[dict[str, str]]

    def ranks(self) -> list[int | None]:
        return [query.rank for query in self.queries]

    def as_payload(self) -> dict[str, Any]:
        by_deg = group_ranks((query.degradation, query.rank) for query in self.queries)
        return {
            "split": self.split,
            "protocol": self.protocol,
            "scorer": self.scorer.as_payload(),
            "gallery_size": _gallery_size(self.queries),
            "overall": retrieval_block(self.ranks()),
            "by_degradation": {
                name: retrieval_block(by_deg.get(name, [])) for name in DEGRADATION_NAMES
            },
            "wall_seconds": round(self.wall_seconds, 6),
            "images_scored": self.images_scored,
            "not_computed": list(self.not_computed),
            "queries": [
                {
                    "query_id": query.query_id,
                    "target_id": query.target_id,
                    "degradation": query.degradation,
                    "query_image": query.query_image,
                    "reference_image": query.reference_image,
                    "rank": query.rank,
                    "target_score": query.target_score,
                    "top": [
                        {
                            "item_id": row.item_id,
                            "score": round(row.score, 6),
                            "correct": row.correct,
                            "image_name": row.image_name,
                        }
                        for row in query.ranking[:10]
                    ],
                }
                for query in self.queries
            ],
        }


def _gallery_size(queries: list[QueryResult]) -> int:
    if not queries:
        return 0
    return len(queries[0].ranking)


def _read_kind(name: str) -> bytes:
    path = KIND_IMAGES / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_bytes()


def _kind_items(splits: SplitSet, split: str) -> list[SplitItem]:
    return [item for item in splits.items if item.split == split and item.family == "kind_listing"]


def run_retrieval(splits: SplitSet, *, split: str) -> RetrievalReport:
    """Rank each split listing's second photograph against that split's gallery.

    Gallery: image *_1 of every listing in this split.
    Query: image *_2 of the target listing, degraded seven ways.
    A hit is the correct listing identity at rank k. Same-split only: a
    listing assigned to the other split is neither a query nor a distractor.
    """
    protocol = (
        "Closed-set listing retrieval on authorized KIND fixture photographs. "
        "One gallery photograph per listing (local image index 1). The query "
        "is a different photograph of the same listing (index 2) under the "
        "seven degradations named in artifacts/searcher-match-calibration."
        "receipt.json. Rank by the declared visual scorer. An item from the "
        "other split is not present in this gallery."
    )
    scorer = resolve_scorer()
    items = _kind_items(splits, split)
    not_computed: list[dict[str, str]] = []
    gallery: list[tuple[SplitItem, str, bytes]] = []
    queries_spec: list[tuple[SplitItem, str, bytes]] = []
    for item in items:
        if len(item.images) < 2:
            not_computed.append(
                {
                    "id": item.item_id,
                    "reason": "listing has fewer than two authorized photographs",
                }
            )
            continue
        gallery.append((item, item.images[0], _read_kind(item.images[0])))
        queries_spec.append((item, item.images[1], _read_kind(item.images[1])))

    started = time.perf_counter()
    images_scored = 0
    results: list[QueryResult] = []
    gallery_bytes = {item.item_id: blob for item, _name, blob in gallery}
    for item, query_name, query_src in queries_spec:
        for degradation in DEGRADATION_NAMES:
            query_bytes = apply_degradation(query_src, degradation)
            ranked: list[RankedCandidate] = []
            for other, other_name, other_bytes in gallery:
                score = scorer.score(query_bytes, other_bytes)
                images_scored += 1
                ranked.append(
                    RankedCandidate(
                        item_id=other.item_id,
                        score=score,
                        correct=other.item_id == item.item_id,
                        image_name=other_name,
                    )
                )
            ranked.sort(key=lambda row: (-row.score, row.item_id))
            rank: int | None = None
            target_score: float | None = None
            for index, row in enumerate(ranked, start=1):
                if row.correct:
                    rank = index
                    target_score = row.score
                    break
            results.append(
                QueryResult(
                    query_id=f"{item.item_id}:{degradation}",
                    target_id=item.item_id,
                    degradation=degradation,
                    query_image=query_name,
                    reference_image=item.images[0],
                    query_bytes=query_bytes,
                    rank=rank,
                    target_score=target_score,
                    ranking=ranked,
                    gallery_bytes=gallery_bytes,
                )
            )
    wall = time.perf_counter() - started
    if _gallery_size(results) < 10:
        not_computed.append(
            {
                "id": "recall@10_vs_gallery",
                "reason": (
                    f"gallery size is {_gallery_size(results)}; recall@10 equals "
                    "recall@gallery when every listing is ranked"
                ),
            }
        )
    return RetrievalReport(
        split=split,
        scorer=scorer,
        protocol=protocol,
        queries=results,
        wall_seconds=wall,
        images_scored=images_scored,
        not_computed=not_computed,
    )
