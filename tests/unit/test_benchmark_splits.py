"""An identifier may appear in exactly one split."""

from __future__ import annotations

import pytest
from benchmark.splits import (
    CALIBRATION,
    HELD_OUT,
    KNOWN_ITEM_TARGET,
    SplitLeakageError,
    assert_no_leakage,
    assign_splits,
    hardneg_item_id,
    kind_item_id,
    load_canonical_splits,
)


def test_canonical_splits_have_no_shared_identifier() -> None:
    splits = load_canonical_splits()
    assert_no_leakage(splits.calibration_ids, splits.held_out_ids)
    overlap = set(splits.calibration_ids) & set(splits.held_out_ids)
    assert overlap == set()
    assert splits.calibration_ids
    assert splits.held_out_ids


def test_leakage_guard_fails_when_identifier_repeats() -> None:
    with pytest.raises(SplitLeakageError, match="more than one split"):
        assert_no_leakage(["kind:a", "kind:b"], ["kind:b", "hardneg:x"])


def test_leakage_guard_fails_when_identifier_also_in_hidden() -> None:
    with pytest.raises(SplitLeakageError, match="more than one split"):
        assert_no_leakage(["kind:a"], ["kind:b"], hidden=["kind:a"])


def test_leakage_guard_fails_on_empty_reporting_split() -> None:
    with pytest.raises(SplitLeakageError, match="empty"):
        assert_no_leakage(["kind:a"], [])


def test_frozen_manifest_matches_stated_rule() -> None:
    frozen = load_canonical_splits()
    built = assign_splits()
    assert set(frozen.calibration_ids) == set(built.calibration_ids)
    assert set(frozen.held_out_ids) == set(built.held_out_ids)


def test_known_item_target_is_held_out() -> None:
    splits = load_canonical_splits()
    target = kind_item_id(KNOWN_ITEM_TARGET)
    assert target in splits.held_out_ids
    assert target not in splits.calibration_ids


def test_replica_case_is_only_in_held_out() -> None:
    splits = load_canonical_splits()
    replica = hardneg_item_id("replica_copied_title")
    assert replica in splits.held_out_ids
    assert replica not in splits.calibration_ids


def test_every_item_states_source_and_permission() -> None:
    splits = load_canonical_splits()
    for item in splits.items:
        assert item.source
        assert item.permission
        assert item.split in {CALIBRATION, HELD_OUT}
        assert item.item_id
        assert "operator" in item.permission.lower() or "not an operator" in item.permission.lower()
