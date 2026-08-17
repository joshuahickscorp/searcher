"""Splits must be disjoint in pixels, not only in identifiers.

`assert_no_leakage` compares identifiers, which are cheap to keep distinct and
say nothing about content. Measured at commit 73ffb4a, 22 image digests
appeared in both calibration and held_out - `copied_product_code` shares
renders with `adjacent_model` and `two_items` - because the synthetic cases
are built from shared building blocks.

The split boundary now assigns connected render groups wholly to one side,
so calibration and held-out no longer share image content.
"""

from __future__ import annotations

import pytest
from benchmark.corpus import images_for
from benchmark.splits import (
    BUCKET_TRUTH,
    SplitLeakageError,
    assert_no_pixel_leakage,
    assign_splits,
    hardneg_item_id,
)


def _images_by_case() -> dict[str, list[bytes]]:
    return {case: [png for _n, png, _r in images_for(case)] for case in sorted(BUCKET_TRUTH)}


def test_the_guard_detects_shared_pixels() -> None:
    """The guard itself works, independent of the corpus it is pointed at."""
    shared = b"\x89PNG-identical-bytes"
    with pytest.raises(SplitLeakageError):
        assert_no_pixel_leakage({"a": [shared], "b": [shared]}, ["a"], ["b"])


def test_the_guard_passes_on_disjoint_pixels() -> None:
    assert_no_pixel_leakage({"a": [b"one"], "b": [b"two"]}, ["a"], ["b"])


@pytest.mark.xfail(
    reason=(
        "The split is degenerate, not clean. Grouping by render provenance moved every "
        "hard-negative case to held_out, leaving calibration with none, so the guard "
        "refuses the comparison instead of reporting a hollow zero. The real repair is a "
        "boundary that keeps hard negatives on both sides while sharing no pixels, which "
        "may need additional distinct renders rather than reassigning existing cases."
    ),
    strict=True,
)
def test_committed_corpus_has_no_pixel_leakage() -> None:
    splits = assign_splits()
    cal = {c for c in BUCKET_TRUTH if hardneg_item_id(c) in set(splits.calibration_ids)}
    held = {c for c in BUCKET_TRUTH if hardneg_item_id(c) in set(splits.held_out_ids)}
    assert_no_pixel_leakage(_images_by_case(), cal, held)


def test_the_guard_refuses_a_degenerate_comparison() -> None:
    """An empty side makes "no shared pixels" vacuous, not true.

    The committed corpus reached zero shared digests by moving every
    hard-negative case to held_out, leaving calibration with none. The guard
    passed, the number read like a repair, and it proved nothing. A guard that
    cannot tell "disjoint" from "empty" is worse than no guard, because it
    reports success either way.
    """
    with pytest.raises(SplitLeakageError, match="degenerate"):
        assert_no_pixel_leakage({"a": [b"one"]}, [], ["a"])
    with pytest.raises(SplitLeakageError, match="degenerate"):
        assert_no_pixel_leakage({"a": [b"one"]}, ["a"], [])


def test_the_committed_corpus_split_is_degenerate() -> None:
    """Recorded, not hidden: calibration currently holds no hard negatives."""
    splits = assign_splits()
    cal = {c for c in BUCKET_TRUTH if hardneg_item_id(c) in set(splits.calibration_ids)}
    held = {c for c in BUCKET_TRUTH if hardneg_item_id(c) in set(splits.held_out_ids)}
    assert held, "held_out must carry hard negatives"
    assert not cal, (
        "calibration has gained hard negatives - if this now fails, the split was "
        "genuinely repaired and test_committed_corpus_has_no_pixel_leakage becomes "
        "a real check rather than a vacuous one"
    )
