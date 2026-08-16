"""Fifty sequential searches against a real API; report resource growth."""

from __future__ import annotations

import ctypes
import io
import json
from collections.abc import Iterator
from ctypes import Structure, byref, c_int, c_uint64, c_void_p, sizeof
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from tests.support.live_api import LiveApi, live_api, wait_terminal

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "artifacts" / "hardening" / "soak.json"

_PROC_PIDTASKINFO = 4
_PROC_PIDLISTFDS = 1


class _ProcTaskInfo(Structure):
    _fields_ = [
        ("pti_virtual_size", c_uint64),
        ("pti_resident_size", c_uint64),
        ("pti_total_user", c_uint64),
        ("pti_total_system", c_uint64),
        ("pti_threads_user", c_uint64),
        ("pti_threads_system", c_uint64),
        ("pti_policy", c_int),
        ("pti_faults", c_int),
        ("pti_pageins", c_int),
        ("pti_cow_faults", c_int),
        ("pti_messages_sent", c_int),
        ("pti_messages_received", c_int),
        ("pti_syscalls_mach", c_int),
        ("pti_syscalls_unix", c_int),
        ("pti_csw", c_int),
        ("pti_threadnum", c_int),
        ("pti_numrunning", c_int),
        ("pti_priority", c_int),
    ]


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), (20, 30, 40)).save(buf, format="PNG")
    return buf.getvalue()


def _ps(pid: int) -> dict[str, int]:
    """RSS and open-file count via libproc (ps/lsof are blocked in the sandbox)."""
    lib = ctypes.CDLL("/usr/lib/libproc.dylib")
    lib.proc_pidinfo.argtypes = [c_int, c_int, c_uint64, c_void_p, c_int]
    lib.proc_pidinfo.restype = c_int
    info = _ProcTaskInfo()
    got = lib.proc_pidinfo(pid, _PROC_PIDTASKINFO, 0, byref(info), sizeof(info))
    rss_kb = int(info.pti_resident_size // 1024) if got > 0 else -1
    buf = ctypes.create_string_buffer(64 * 1024)
    fd_bytes = lib.proc_pidinfo(pid, _PROC_PIDLISTFDS, 0, buf, len(buf))
    fds = int(fd_bytes // 8) if fd_bytes > 0 else -1
    return {"rss_kb": rss_kb, "fds": fds}


@pytest.fixture(scope="module")
def api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LiveApi]:
    root = tmp_path_factory.mktemp("soak-api")
    with live_api(root) as server:
        yield server


@pytest.mark.timeout(360)
def test_fifty_sequential_searches_do_not_grow_without_bound(api: LiveApi) -> None:
    db_path = api.data_root / "searcher.sqlite"
    before = _ps(api.pid)
    before["db_bytes"] = db_path.stat().st_size if db_path.is_file() else 0
    png = _png()
    terminals: list[str] = []
    with api.client(timeout=30.0) as client:
        health = client.get("/v1/health")
        assert health.status_code == 200
        for index in range(50):
            files: list[tuple[str, Any]] = [
                ("images", (f"ref-{index}.png", png, "image/png")),
                ("text", (None, "Dior Homme General Army Trainer")),
                ("tags", (None, "dior")),
            ]
            created = client.post("/v1/searches", files=files)
            assert created.status_code == 201, created.text
            search_id = created.json()["search_id"]
            terminal = wait_terminal(client, search_id, timeout=40.0)
            assert terminal["terminal_status"] == "BLOCKED"
            terminals.append(str(terminal["terminal_status"]))
            if index in {0, 24, 49}:
                mid = _ps(api.pid)
                mid["db_bytes"] = db_path.stat().st_size
                mid["completed"] = index + 1
                (REPORT.parent / f"soak-mid-{index + 1}.json").parent.mkdir(
                    parents=True, exist_ok=True
                )
                (REPORT.parent / f"soak-mid-{index + 1}.json").write_text(
                    json.dumps(mid, indent=2, sort_keys=True), encoding="utf-8"
                )
    after = _ps(api.pid)
    after["db_bytes"] = db_path.stat().st_size
    report = {
        "searches": 50,
        "terminal": terminals[-1] if terminals else None,
        "all_blocked": all(item == "BLOCKED" for item in terminals),
        "before": before,
        "after": after,
        "rss_delta_kb": after["rss_kb"] - before["rss_kb"],
        "fd_delta": after["fds"] - before["fds"] if after["fds"] >= 0 else None,
        "db_delta_bytes": after["db_bytes"] - before["db_bytes"],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    assert len(terminals) == 50
    assert all(item == "BLOCKED" for item in terminals)
    # Level-off: fifty searches may grow the DB, but RSS/FDs must not run away.
    assert after["rss_kb"] < before["rss_kb"] + 400_000
    if after["fds"] >= 0 and before["fds"] >= 0:
        assert after["fds"] < before["fds"] + 80
    assert after["db_bytes"] < before["db_bytes"] + 80_000_000
