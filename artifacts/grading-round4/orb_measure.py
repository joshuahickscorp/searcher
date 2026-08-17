# ruff: noqa: E501
"""Independent ORB vs fallback measurement on fixtures/user_snapshots.

A command that fails if the claimed TPR 1.000 / FPR 0.000 at threshold 10
does not hold for the currently selected detector.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

from searcher.matching.correspondence import correspond_pair
from searcher.matching.features import opencv_available

SNAPSHOTS = Path("fixtures/user_snapshots")
LISTINGS = Path("fixtures/known_item_kind/images")
THRESHOLD = 10


def main() -> int:
    manifest = json.loads((SNAPSHOTS / "MANIFEST.json").read_text())
    items = manifest["items"]
    same: list[int] = []
    other: list[int] = []
    pairs: list[dict[object, object]] = []
    methods: set[str] = set()
    for i, row in enumerate(items):
        snap = (SNAPSHOTS / row["snapshot"]).read_bytes()
        own_listing = (LISTINGS / row["derived_from"]).read_bytes()
        other_row = items[(i + 1) % len(items)]
        other_listing = (LISTINGS / other_row["derived_from"]).read_bytes()
        own = correspond_pair(snap, own_listing)
        alt = correspond_pair(snap, other_listing)
        methods.add(own.method)
        methods.add(alt.method)
        same.append(own.inlier_count)
        other.append(alt.inlier_count)
        pairs.append(
            {
                "snapshot": row["snapshot"],
                "own_listing": row["derived_from"],
                "other_listing": other_row["derived_from"],
                "own_inliers": own.inlier_count,
                "other_inliers": alt.inlier_count,
                "own_method": own.method,
                "other_method": alt.method,
                "own_notes": own.notes,
                "other_notes": alt.notes,
            }
        )
    tp = sum(1 for n in same if n >= THRESHOLD)
    fn = len(same) - tp
    fp = sum(1 for n in other if n >= THRESHOLD)
    tn = len(other) - fp
    tpr = tp / len(same) if same else 0.0
    fpr = fp / len(other) if other else 0.0
    payload = {
        "opencv_available": opencv_available(),
        "methods": sorted(methods),
        "n": len(items),
        "threshold": THRESHOLD,
        "same_inliers": same,
        "other_inliers": other,
        "same_median": statistics.median(same) if same else None,
        "other_median": statistics.median(other) if other else None,
        "same_min": min(same) if same else None,
        "same_max": max(same) if same else None,
        "other_min": min(other) if other else None,
        "other_max": max(other) if other else None,
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "tpr": round(tpr, 3),
        "fpr": round(fpr, 3),
        "honest_limits": manifest.get("honest_limits"),
        "pairs": pairs,
    }
    out = Path("artifacts/grading-round4/orb_measure.json")
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({k: payload[k] for k in payload if k != "pairs"}, indent=2))
    if not opencv_available():
        print("CLAIM_FAIL: opencv is not available; ORB claim cannot hold in this process")
        return 2
    if methods != {"orb"}:
        print(f"CLAIM_FAIL: expected method orb, got {methods}")
        return 3
    if tpr != 1.0 or fpr != 0.0:
        print(f"CLAIM_FAIL: TPR={tpr:.3f} FPR={fpr:.3f} (want 1.000 / 0.000)")
        return 4
    print("CLAIM_HOLD: ORB TPR=1.000 FPR=0.000 at threshold 10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
