"""Light probe and import isolation."""

from __future__ import annotations

import sys
import time

from searcher.core.capabilities import CapabilityName
from searcher.integrations.visionmcp.compatibility import PINNED_SHA, PINNED_VERSION
from searcher.integrations.visionmcp.probe import probe_timed


def test_import_searcher_does_not_import_torch() -> None:
    # searcher is already imported by pytest collection; torch/cv2 must still be absent.
    assert "torch" not in sys.modules
    assert "cv2" not in sys.modules
    assert "playwright" not in sys.modules


def test_probe_is_fast_and_covers_all_names() -> None:
    report, elapsed = probe_timed()
    names = {record.name for record in report.capabilities}
    assert names == set(CapabilityName)
    assert elapsed < 2.0
    receipt = next(r for r in report.capabilities if r.name is CapabilityName.RECEIPT_VERIFY)
    assert receipt.available
    dense = next(r for r in report.capabilities if r.name is CapabilityName.DENSE_FEATURES)
    assert not dense.available
    assert PINNED_SHA.startswith("18ee3c06")
    assert PINNED_VERSION == "0.8.0a2"


def test_probe_does_not_load_heavy_modules() -> None:
    probe_timed()
    assert "torch" not in sys.modules
    assert "cv2" not in sys.modules
    assert "playwright" not in sys.modules


def test_probe_wall_clock_budget() -> None:
    started = time.perf_counter()
    probe_timed()
    assert time.perf_counter() - started < 2.0
