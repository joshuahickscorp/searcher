"""Separation must never be publishable as a single flattering number.

I reported +0.690816 for multi-view separation. Round 5 recomputed it over
every negative, got -0.099184, and called the claim unreproduced. Both are
arithmetically right: the difference is whether `stolen_photos` counts as a
different-item negative. It reuses the target's own photographs, so a high item
match is the correct answer there and a stolen-photo veto is what hides it -
the exclusion is defensible, and quoting the result without saying so was not.

The receipt now carries both, so the favourable one cannot travel alone.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RECEIPT = Path("artifacts/searcher-public-benchmark.receipt.json")


def _separation() -> dict:
    if not RECEIPT.is_file():
        pytest.skip("benchmark receipt has not been generated on this host")
    block = json.loads(RECEIPT.read_text(encoding="utf-8"))["buckets"].get("item_match_separation")
    assert block is not None, "the bucket payload must publish item_match_separation"
    return block


def test_both_separations_are_published() -> None:
    block = _separation()
    if not block.get("computed"):
        pytest.skip(block.get("reason", "separation not computed"))
    assert "over_every_negative" in block
    assert "over_different_item_negatives" in block


def test_every_exclusion_is_named_and_justified() -> None:
    block = _separation()
    if not block.get("computed"):
        pytest.skip(block.get("reason", "separation not computed"))
    excluded = block["excluded_from_different_item"]
    if excluded:
        assert block.get("why_excluded"), "an exclusion without a stated reason is a bare number"
        for case in excluded:
            assert case in block["why_excluded"], f"{case} is excluded but never explained"
