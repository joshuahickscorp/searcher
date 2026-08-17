"""Splits must be disjoint in pixels, not only in identifiers.

`assert_no_leakage` compares identifiers, which are cheap to keep distinct and
say nothing about content. Measured on the committed corpus, 22 image digests
appear in both calibration and held_out - `copied_product_code` shares renders
with `adjacent_model` and `two_items` - because the synthetic cases are built
from shared building blocks.

Any pixel-based scorer has therefore seen held-out images while being
calibrated, so held-out numbers are measured partly on their own tuning data.
This test states the property. It is expected to fail until the split boundary
respects render provenance; that failure is the finding, not a flaw in the test.
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
        "The committed corpus shares 22 image digests between calibration and held_out. "
        "Recorded as a known contamination rather than hidden; the repair is to make the "
        "split boundary respect render provenance, which drops no case."
    ),
    strict=True,
)
def test_committed_corpus_has_no_pixel_leakage() -> None:
    splits = assign_splits()
    cal = {c for c in BUCKET_TRUTH if hardneg_item_id(c) in set(splits.calibration_ids)}
    held = {c for c in BUCKET_TRUTH if hardneg_item_id(c) in set(splits.held_out_ids)}
    assert_no_pixel_leakage(_images_by_case(), cal, held)
