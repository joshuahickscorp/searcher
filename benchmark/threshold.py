"""Choose the pair threshold on the calibration split, report it on held-out.

`calibration.py` deliberately never retunes: it describes where the shipped
threshold falls. This module is the other half — it picks an operating point
from labelled data that lives in this repository, then reports what that point
does on data it never saw.

Run it:

    uv run python -m benchmark.threshold

The point of separating the two splits is that a threshold chosen on the same
pairs it is judged on tells you nothing. Every number here names the split it
came from.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import SHIPPED_THRESHOLD
from .calibration import pair_scores
from .hostinfo import run_identity
from .scores import Scorer, resolve_scorer
from .splits import SplitSet, load_canonical_splits

# A false Real is the expensive error: it tells someone a replica or an
# unrelated garment is the item they are hunting. Recall is worth less than
# that, so the operating point is chosen under a false-positive ceiling.
TARGET_FPR = 0.05


def rates(
    pairs: list[tuple[float, bool, str, str]], threshold: float
) -> tuple[float, float, int, int]:
    positives = [p for p in pairs if p[1]]
    negatives = [p for p in pairs if not p[1]]
    tpr = sum(1 for p in positives if p[0] >= threshold) / len(positives) if positives else 0.0
    fpr = sum(1 for n in negatives if n[0] >= threshold) / len(negatives) if negatives else 0.0
    return tpr, fpr, len(positives), len(negatives)


def sweep(pairs: list[tuple[float, bool, str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in range(40, 100):
        threshold = step / 100
        tpr, fpr, n_pos, n_neg = rates(pairs, threshold)
        rows.append(
            {
                "threshold": round(threshold, 2),
                "tpr": round(tpr, 4),
                "fpr": round(fpr, 4),
                "n_positive": n_pos,
                "n_negative": n_neg,
            }
        )
    return rows


def choose(rows: list[dict[str, Any]], target_fpr: float = TARGET_FPR) -> dict[str, Any] | None:
    """Lowest threshold whose false-positive rate is within the ceiling.

    Lowest, not best-F1: among points that respect the ceiling, the one that
    admits the most true pairs is the one that finds the most items.
    """
    allowed = [row for row in rows if row["fpr"] <= target_fpr]
    if not allowed:
        return None
    best = max(allowed, key=lambda row: (row["tpr"], -row["threshold"]))
    return best


def _flip_splits(splits: SplitSet) -> SplitSet:
    """The same items with the two split labels exchanged."""
    from dataclasses import replace

    from .splits import CALIBRATION, HELD_OUT

    swapped = tuple(
        replace(item, split=CALIBRATION if item.split == HELD_OUT else HELD_OUT)
        for item in splits.items
    )
    return SplitSet(rule=splits.rule, items=swapped)


def run(splits: SplitSet, scorer: Scorer) -> dict[str, Any]:
    calibration_pairs = pair_scores(splits, scorer)
    calibration_rows = sweep(calibration_pairs)
    chosen = choose(calibration_rows)

    # pair_scores reads the calibration side, so present the held-out items as
    # that side rather than duplicating the pairing logic.
    flipped = _flip_splits(splits)
    held_out_pairs = pair_scores(flipped, scorer)

    chosen_threshold = chosen["threshold"] if chosen else None
    held_tpr, held_fpr, held_pos, held_neg = (
        rates(held_out_pairs, chosen_threshold)
        if chosen_threshold is not None
        else (0.0, 0.0, 0, 0)
    )
    shipped_tpr, shipped_fpr, _p, _n = rates(held_out_pairs, SHIPPED_THRESHOLD)

    verdict = "no threshold on the calibration split meets the ceiling"
    if chosen_threshold is not None:
        separates = held_fpr <= target_ceiling() and held_tpr > 0.0
        verdict = (
            "chosen threshold holds on held-out data"
            if separates
            else "chosen threshold does not hold on held-out data"
        )

    return {
        "protocol": (
            "Pair scores from authorized KIND listing photographs. A positive "
            "pair is two photographs of one listing; a negative pair is one "
            "photograph each of two different listings. The threshold is chosen "
            "on the calibration split under a false-positive ceiling and then "
            "reported on the held-out split, which was not used to choose it."
        ),
        "scorer": scorer.identity,
        "target_fpr": TARGET_FPR,
        "calibration": {
            "n_positive_pairs": chosen["n_positive"] if chosen else 0,
            "n_negative_pairs": chosen["n_negative"] if chosen else 0,
            "sweep": calibration_rows,
            "chosen": chosen,
        },
        "held_out": {
            "threshold": chosen_threshold,
            "tpr": round(held_tpr, 4),
            "fpr": round(held_fpr, 4),
            "n_positive_pairs": held_pos,
            "n_negative_pairs": held_neg,
        },
        "shipped_threshold": {
            "value": SHIPPED_THRESHOLD,
            "held_out_tpr": round(shipped_tpr, 4),
            "held_out_fpr": round(shipped_fpr, 4),
        },
        "verdict": verdict,
        "identity": run_identity(),
    }


def target_ceiling() -> float:
    return TARGET_FPR


def main() -> int:
    splits = load_canonical_splits()
    scorer = resolve_scorer()
    report = run(splits, scorer)
    out = Path("artifacts/searcher-threshold.receipt.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")

    chosen = report["calibration"]["chosen"]
    print("scorer:", report["scorer"])
    if chosen:
        print(f"chosen on calibration: {chosen['threshold']} "
              f"(tpr {chosen['tpr']}, fpr {chosen['fpr']}, "
              f"{chosen['n_positive']}+/{chosen['n_negative']}-)")
    else:
        print("no threshold met the ceiling on the calibration split")
    held = report["held_out"]
    print(f"held out at {held['threshold']}: tpr {held['tpr']}, fpr {held['fpr']} "
          f"({held['n_positive_pairs']}+/{held['n_negative_pairs']}-)")
    shipped = report["shipped_threshold"]
    print(f"shipped {shipped['value']} on held out: "
          f"tpr {shipped['held_out_tpr']}, fpr {shipped['held_out_fpr']}")
    print("verdict:", report["verdict"])
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
