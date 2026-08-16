"""Bucket-decision metrics against constructed hard-negative labels."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from searcher.campaigns.publication import published_public_bucket
from searcher.ranking.pipeline import judge_candidates

from .corpus import build_cases, hypothesis_for, reference_pngs
from .metrics import BUCKET_LABELS, false_real_report, precision_recall
from .splits import BUCKET_TRUTH, SplitSet, hardneg_item_id


@dataclass
class BucketRow:
    item_id: str
    case_id: str
    truth: str
    predicted: str
    item_match_lower: float
    authenticity_lower: float
    completeness: float
    reasons: list[str]
    hard_vetoes: list[str]
    preview: bytes | None
    reference_preview: bytes | None
    correct: bool


@dataclass
class BucketReport:
    split: str
    protocol: str
    rows: list[BucketRow]
    wall_seconds: float
    fetches: int
    cache_hits: int
    images_processed: int
    not_computed: list[dict[str, str]]

    def as_payload(self) -> dict[str, Any]:
        pairs = [(row.truth, row.predicted) for row in self.rows]
        precision, recall, matrix = precision_recall(pairs)
        false_real = false_real_report((row.item_id, row.truth, row.predicted) for row in self.rows)
        return {
            "split": self.split,
            "protocol": self.protocol,
            "labels": list(BUCKET_LABELS),
            "n": len(self.rows),
            "precision": _round_optional(precision),
            "recall": _round_optional(recall),
            "confusion": matrix,
            "false_real": {
                **false_real,
                "rate_among_all": _round(false_real["rate_among_all"]),
                "rate_among_not_real": _round(false_real["rate_among_not_real"]),
            },
            "rows": [
                {
                    "id": row.item_id,
                    "case_id": row.case_id,
                    "truth": row.truth,
                    "predicted": row.predicted,
                    "correct": row.correct,
                    "item_match_lower": row.item_match_lower,
                    "authenticity_lower": row.authenticity_lower,
                    "completeness": row.completeness,
                    "reasons": row.reasons,
                    "hard_vetoes": row.hard_vetoes,
                }
                for row in self.rows
            ],
            "wall_seconds": round(self.wall_seconds, 6),
            "fetches": self.fetches,
            "cache_hits": self.cache_hits,
            "images_processed": self.images_processed,
            "not_computed": list(self.not_computed),
        }


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _round_optional(mapping: dict[str, float | None]) -> dict[str, float | None]:
    return {key: _round(value) for key, value in mapping.items()}


def run_buckets(splits: SplitSet, *, split: str) -> BucketReport:
    protocol = (
        "Bucket decision on the constructed hard-negative corpus. Labels come "
        "from the fixture recipe (same shoe, adjacent model, self-declared "
        "replica, dead listing, ...), not from a marketplace badge and not "
        "from a professional authenticator. Predictions are "
        "searcher.ranking.pipeline.judge_candidates followed by "
        "published_public_bucket so a self-declared replica is scored as "
        "Replica rather than Hidden. Policy version is matching-1. This is "
        "not an authenticity-accuracy claim."
    )
    items = [
        item for item in splits.items if item.split == split and item.family == "hard_negative"
    ]
    case_ids = [item.item_id.split(":", 1)[1] for item in items]
    cases = build_cases(case_ids, BUCKET_TRUTH)
    by_id = {case.case_id: case for case in cases}
    ordered = [by_id[case_id] for case_id in case_ids]
    hyp, cons = hypothesis_for(ordered)
    ref = reference_pngs()
    candidates = [case.candidate for case in ordered]
    pngs = {case.case_id: case.pngs for case in ordered}
    dest = {case.case_id: True for case in ordered}
    stolen = {case.case_id for case in ordered if case.stolen}

    started = time.perf_counter()
    report = judge_candidates(
        search_id=hyp.search_id,
        hypothesis=hyp,
        candidates=candidates,
        reference_pngs=ref,
        candidate_pngs=pngs,
        constraints=cons,
        already_deduplicated=True,
        destination_verified=dest,
        stolen=stolen,
        render_artifacts=False,
    )
    wall = time.perf_counter() - started
    by_bundle = {bundle.candidate.candidate_id: bundle for bundle in report.bundles}
    ref_preview = next(iter(ref.values()), None)
    rows: list[BucketRow] = []
    not_computed: list[dict[str, str]] = []
    images_processed = sum(len(case.pngs) for case in ordered) + len(ref)
    for case in ordered:
        bundle = by_bundle.get(case.case_id)
        if bundle is None:
            not_computed.append(
                {
                    "id": hardneg_item_id(case.case_id),
                    "reason": "candidate dropped before a bucket decision",
                }
            )
            predicted = "hidden"
            reasons: list[str] = ["dropped-before-decision"]
            vetoes: list[str] = []
            item_lb = 0.0
            auth_lb = 0.0
            complete = 0.0
            preview = next(iter(case.pngs.values()), None)
        else:
            predicted = published_public_bucket(bundle.decision, bundle.candidate)
            reasons = list(bundle.decision.reason_codes)
            vetoes = list(bundle.decision.hard_vetoes)
            item_lb = float(bundle.decision.item_match_lower_bound)
            auth_lb = float(bundle.decision.authenticity_lower_bound)
            complete = float(bundle.decision.evidence_completeness)
            preview = next(iter(case.pngs.values()), None)
        rows.append(
            BucketRow(
                item_id=hardneg_item_id(case.case_id),
                case_id=case.case_id,
                truth=case.truth,
                predicted=predicted,
                item_match_lower=item_lb,
                authenticity_lower=auth_lb,
                completeness=complete,
                reasons=reasons,
                hard_vetoes=vetoes,
                preview=preview,
                reference_preview=ref_preview,
                correct=predicted == case.truth,
            )
        )
    present = {row.truth for row in rows}
    for label in BUCKET_LABELS:
        if label not in present:
            not_computed.append(
                {
                    "id": f"bucket:{label}",
                    "reason": f"no constructed {label} label in the {split} split",
                }
            )
    return BucketReport(
        split=split,
        protocol=protocol,
        rows=rows,
        wall_seconds=wall,
        fetches=0,
        cache_hits=report.ledger.cache_hits,
        images_processed=images_processed,
        not_computed=not_computed,
    )
