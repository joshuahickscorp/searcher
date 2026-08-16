"""Light probe and import isolation."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from searcher.core.capabilities import CapabilityName
from searcher.integrations.visionmcp.compatibility import PINNED_SHA, PINNED_VERSION
from searcher.integrations.visionmcp.probe import probe_timed

HEAVY = ("torch", "cv2", "playwright")

# These two run in a fresh interpreter on purpose. Asserting against this
# process's sys.modules only holds when no earlier test in the session has
# imported a heavy module, which made the check pass alone and fail in a full
# run — the weaker reading of a real invariant.
_IMPORT_ONLY = "import searcher, sys; print(','.join(m for m in {heavy} if m in sys.modules))"
_WITH_PROBE = (
    "import sys; from searcher.integrations.visionmcp.probe import probe_timed; "
    "probe_timed(); print(','.join(m for m in {heavy} if m in sys.modules))"
)


def _heavy_modules_after(snippet: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", snippet.format(heavy=HEAVY)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_import_searcher_does_not_import_torch() -> None:
    assert _heavy_modules_after(_IMPORT_ONLY) == ""


def test_probe_is_fast_and_covers_all_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Dense features depend on weights being installed on the host. Point the
    # gateway at an empty root so this asserts the donor's contribution, not
    # whatever happens to be on this machine.
    monkeypatch.delenv("SEARCHER_EMBEDDING_WEIGHTS", raising=False)
    monkeypatch.setenv("SEARCHER_DATA_ROOT", str(tmp_path))
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
    assert _heavy_modules_after(_WITH_PROBE) == ""


def test_probe_wall_clock_budget() -> None:
    started = time.perf_counter()
    probe_timed()
    assert time.perf_counter() - started < 2.0
