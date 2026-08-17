# ruff: noqa: E501
"""Measure the BRIEF fallback on the same snapshot pairs, with opencv hidden."""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

import searcher.matching.features as features
from searcher.matching.correspondence import correspond_pair

SNAPSHOTS = Path("fixtures/user_snapshots")
LISTINGS = Path("fixtures/known_item_kind/images")
THRESHOLD = 10


def main() -> int:
    features.opencv_available = lambda: False  # type: ignore[assignment]
    manifest = json.loads((SNAPSHOTS / "MANIFEST.json").read_text())
    items = manifest["items"]
    same: list[int] = []
    other: list[int] = []
    methods: set[str] = set()
    for i, row in enumerate(items):
        snap = (SNAPSHOTS / row["snapshot"]).read_bytes()
        own_listing = (LISTINGS / row["derived_from"]).read_bytes()
        other_row = items[(i + 1) % len(items)]
        other_listing = (LISTINGS / other_row["derived_from"]).read_bytes()
        own = correspond_pair(snap, own_listing)
        alt = correspond_pair(snap, other_listing)
        methods.add(own.method)
        same.append(own.inlier_count)
        other.append(alt.inlier_count)
    tp = sum(1 for n in same if n >= THRESHOLD)
    fp = sum(1 for n in other if n >= THRESHOLD)
    tpr = tp / len(same)
    fpr = fp / len(other)
    overlap = not (max(other) < min(same))
    payload: dict[str, Any] = {
        "methods": sorted(methods),
        "same_inliers": same,
        "other_inliers": other,
        "same_median": statistics.median(same),
        "other_median": statistics.median(other),
        "same_min": min(same),
        "same_max": max(same),
        "other_min": min(other),
        "other_max": max(other),
        "tpr": round(tpr, 3),
        "fpr": round(fpr, 3),
        "ranges_overlap": overlap,
        "cannot_separate": overlap,
    }
    Path("artifacts/grading-round4/fallback_measure.json").write_text(
        json.dumps(payload, indent=2) + "\n"
    )
    print(json.dumps(payload, indent=2))
    if methods != {"brief_fallback"}:
        print("UNEXPECTED method", methods)
        return 2
    if not overlap:
        print("FALLBACK_SEPARATES contrary to claim")
        return 3
    print("CLAIM_HOLD: fallback ranges overlap; signal is noise")
    return 0


if __name__ == "__main__":
    sys.exit(main())
