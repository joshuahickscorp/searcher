"""Retrieval, bucket, and calibration arithmetic. Pure functions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from . import SHIPPED_THRESHOLD

BUCKET_LABELS: tuple[str, ...] = ("real", "possibly_real", "replica", "hidden")


def recall_at_k(ranks: Iterable[int | None], k: int) -> float:
    values = list(ranks)
    if not values:
        return 0.0
    hits = sum(1 for rank in values if rank is not None and 1 <= rank <= k)
    return hits / len(values)


def mean_reciprocal_rank(ranks: Iterable[int | None]) -> float:
    values = list(ranks)
    if not values:
        return 0.0
    total = 0.0
    for rank in values:
        if rank is not None and rank >= 1:
            total += 1.0 / rank
    return total / len(values)


def retrieval_block(ranks: list[int | None]) -> dict[str, Any]:
    return {
        "n": len(ranks),
        "recall_at_1": round(recall_at_k(ranks, 1), 6),
        "recall_at_5": round(recall_at_k(ranks, 5), 6),
        "recall_at_10": round(recall_at_k(ranks, 10), 6),
        "mrr": round(mean_reciprocal_rank(ranks), 6),
        "missing": sum(1 for rank in ranks if rank is None),
    }


def confusion_matrix(
    pairs: Iterable[tuple[str, str]],
    labels: tuple[str, ...] = BUCKET_LABELS,
) -> dict[str, dict[str, int]]:
    table = {truth: {pred: 0 for pred in labels} for truth in labels}
    for truth, pred in pairs:
        if truth not in table:
            table[truth] = {name: 0 for name in labels}
        if pred not in table[truth]:
            for row in table.values():
                row[pred] = 0
        table[truth][pred] += 1
    return table


def precision_recall(
    pairs: Iterable[tuple[str, str]],
    labels: tuple[str, ...] = BUCKET_LABELS,
) -> tuple[dict[str, float | None], dict[str, float | None], dict[str, dict[str, int]]]:
    rows = list(pairs)
    matrix = confusion_matrix(rows, labels=labels)
    precision: dict[str, float | None] = {}
    recall: dict[str, float | None] = {}
    for label in labels:
        tp = matrix.get(label, {}).get(label, 0)
        pred_pos = sum(row.get(label, 0) for row in matrix.values())
        truth_pos = sum(matrix.get(label, {}).values()) if label in matrix else 0
        precision[label] = None if pred_pos == 0 else tp / pred_pos
        recall[label] = None if truth_pos == 0 else tp / truth_pos
    return precision, recall, matrix


def false_real_report(
    pairs: Iterable[tuple[str, str, str]],
) -> dict[str, Any]:
    """pairs are (item_id, truth, predicted). False Real is the expensive error."""
    rows = list(pairs)
    false_ids = [item_id for item_id, truth, pred in rows if pred == "real" and truth != "real"]
    n = len(rows)
    n_not_real = sum(1 for _item, truth, _pred in rows if truth != "real")
    return {
        "count": len(false_ids),
        "n": n,
        "n_labelled_not_real": n_not_real,
        "rate_among_all": None if n == 0 else len(false_ids) / n,
        "rate_among_not_real": None if n_not_real == 0 else len(false_ids) / n_not_real,
        "ids": false_ids,
        "note": (
            "A false Real is a candidate labelled something other than Real "
            "that the engine published as Real. This is the expensive error."
        ),
    }


def calibration_bins(
    pairs: Iterable[tuple[float, bool]],
    *,
    bin_width: float = 0.1,
    threshold: float = SHIPPED_THRESHOLD,
) -> dict[str, Any]:
    """Score-versus-outcome curve. outcome True means same-listing (positive)."""
    rows = list(pairs)
    edges: list[float] = []
    edge = 0.0
    while edge < 1.0 - 1e-12:
        edges.append(round(edge, 10))
        edge += bin_width
    edges.append(1.0)
    bins: list[dict[str, Any]] = []
    threshold_bin: int | None = None
    for index in range(len(edges) - 1):
        lo = edges[index]
        hi = edges[index + 1]
        closed_hi = index == len(edges) - 2
        in_bin: list[tuple[float, bool]] = []
        for score, positive in rows:
            if closed_hi:
                if lo <= score <= hi:
                    in_bin.append((score, positive))
            elif lo <= score < hi:
                in_bin.append((score, positive))
        n = len(in_bin)
        n_pos = sum(1 for _score, positive in in_bin if positive)
        mean = sum(score for score, _ in in_bin) / n if n else None
        bins.append(
            {
                "index": index,
                "lo": lo,
                "hi": hi,
                "n": n,
                "n_positive": n_pos,
                "n_negative": n - n_pos,
                "positive_rate": None if n == 0 else n_pos / n,
                "mean_score": mean,
            }
        )
        if threshold_bin is None and (
            (closed_hi and lo <= threshold <= hi) or (not closed_hi and lo <= threshold < hi)
        ):
            threshold_bin = index
    return {
        "bin_width": bin_width,
        "n_pairs": len(rows),
        "n_positive": sum(1 for _s, positive in rows if positive),
        "n_negative": sum(1 for _s, positive in rows if not positive),
        "shipped_threshold": threshold,
        "threshold_bin": threshold_bin,
        "bins": bins,
    }


def group_ranks(rows: Iterable[tuple[str, int | None]]) -> dict[str, list[int | None]]:
    grouped: dict[str, list[int | None]] = defaultdict(list)
    for key, rank in rows:
        grouped[key].append(rank)
    return dict(grouped)
