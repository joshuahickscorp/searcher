"""Score-versus-outcome curve on the calibration split. Does not retune."""

from __future__ import annotations

from typing import Any

from . import SHIPPED_THRESHOLD
from .metrics import calibration_bins
from .paths import KIND_IMAGES
from .scores import Scorer
from .splits import SplitSet


def _read(name: str) -> bytes:
    return (KIND_IMAGES / name).read_bytes()


def pair_scores(splits: SplitSet, scorer: Scorer) -> list[tuple[float, bool, str, str]]:
    """Same-listing and different-listing pairs from calibration KIND listings."""
    listings = [
        item
        for item in splits.calibration
        if item.family == "kind_listing" and len(item.images) >= 2
    ]
    pairs: list[tuple[float, bool, str, str]] = []
    for item in listings:
        gallery = _read(item.images[0])
        for other_name in item.images[1:]:
            score = scorer.score(gallery, _read(other_name))
            pairs.append((score, True, item.item_id, f"{item.item_id}:{other_name}"))
    for index, left in enumerate(listings):
        left_bytes = _read(left.images[0])
        for right in listings[index + 1 :]:
            score = scorer.score(left_bytes, _read(right.images[0]))
            pairs.append((score, False, left.item_id, right.item_id))
    return pairs


def run_calibration(splits: SplitSet, scorer: Scorer) -> dict[str, Any]:
    pairs = pair_scores(splits, scorer)
    curve = calibration_bins(((score, positive) for score, positive, _a, _b in pairs))
    threshold_bin = curve["threshold_bin"]
    bin_note = "threshold does not fall in a populated bin range"
    if threshold_bin is not None:
        row = curve["bins"][threshold_bin]
        bin_note = (
            f"shipped threshold {SHIPPED_THRESHOLD} sits in bin "
            f"[{row['lo']}, {row['hi']}] with n={row['n']} "
            f"(positive_rate={row['positive_rate']})"
        )
    return {
        "split": "calibration",
        "protocol": (
            "Pair curve on the calibration KIND listings only. A positive pair "
            "is two different authorized photographs of the same listing. A "
            "negative pair is gallery photograph of listing A versus gallery "
            "photograph of listing B. The shipped 0.86 threshold is taken from "
            "artifacts/searcher-match-calibration.receipt.json and is not "
            "refit on this split."
        ),
        "scorer": scorer.as_payload(),
        "shipped_threshold": SHIPPED_THRESHOLD,
        "threshold_source": "artifacts/searcher-match-calibration.receipt.json",
        "threshold_retuned": False,
        "threshold_bin_note": bin_note,
        "threshold_meaningful_on_this_scale": scorer.threshold_applies,
        "curve": curve,
        "n_pairs": len(pairs),
    }
