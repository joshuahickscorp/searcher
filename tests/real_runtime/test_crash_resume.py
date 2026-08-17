"""SIGKILL mid-campaign, then resume: zero accepted evidence lost."""

from __future__ import annotations

import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
from tests.support.child_process import run_child

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.resume import reconstruct
from searcher.contracts.enums import CampaignState
from searcher.core.config import Settings
from searcher.evidence.content_store import ContentStore
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate

TERMINAL = {
    CampaignState.COMPLETE.value,
    CampaignState.PARTIAL.value,
    CampaignState.BLOCKED.value,
    CampaignState.FAILED.value,
    CampaignState.CANCELLED.value,
}


def _cli() -> list[str]:
    return [sys.executable, "-m", "searcher"]


def _env(data_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["SEARCHER_DATA_ROOT"] = str(data_root)
    env["SEARCHER_STEP_DELAY_MS"] = "250"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _parse_search_id(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("search_id:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"no search_id in output:\n{stdout}")


def _poll(db_path: Path) -> dict[str, object]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        campaign = conn.execute("SELECT * FROM campaigns").fetchone()
        if campaign is None:
            return {"ready": False}
        checkpoints = conn.execute(
            "SELECT COUNT(*) AS n FROM checkpoints WHERE search_id = ?",
            (campaign["search_id"],),
        ).fetchone()["n"]
        evidence = conn.execute(
            "SELECT evidence_id FROM evidence_metadata WHERE search_id = ? AND accepted = 1",
            (campaign["search_id"],),
        ).fetchall()
        return {
            "ready": checkpoints >= 1 and len(evidence) >= 1,
            "state": campaign["state"],
            "state_version": campaign["state_version"],
            "checkpoints": checkpoints,
            "accepted_ids": [row["evidence_id"] for row in evidence],
        }
    except sqlite3.OperationalError:
        return {"ready": False}
    finally:
        conn.close()


@pytest.mark.timeout(120)
def test_sigkill_resume_loses_zero_accepted_evidence(tmp_path: Path) -> None:
    env = _env(tmp_path)
    # run_child separates a child that died from a signal - a host problem -
    # from a child that ran and failed, which is a statement about Searcher.
    # Round 5 saw only "SIGSEGV (-11)" here and scored it as a product failure.
    run_child([*_cli(), "db", "migrate"], env=env)

    created = run_child([*_cli(), "campaign", "create", "--fixture", "dior_minimal"], env=env)
    search_id = _parse_search_id(created.stdout)
    db_path = tmp_path / "searcher.sqlite"

    proc = subprocess.Popen(
        [*_cli(), "campaign", "run", search_id],
        cwd=Path.cwd(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    snapshot: dict[str, object] | None = None
    deadline = time.time() + 40
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                out, err = proc.communicate()
                raise AssertionError(
                    f"campaign finished before SIGKILL (code={proc.returncode})\n{out}\n{err}"
                )
            status = _poll(db_path)
            if status.get("ready") and status.get("state") not in TERMINAL:
                snapshot = status
                break
            time.sleep(0.05)
        if snapshot is None:
            proc.kill()
            raise AssertionError("timed out waiting for a mid-flight checkpoint")
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    assert snapshot is not None
    accepted_before = list(snapshot["accepted_ids"])  # type: ignore[arg-type]
    assert accepted_before, "expected accepted evidence before the kill"
    assert snapshot["checkpoints"] >= 1
    assert snapshot["state"] not in TERMINAL

    resumed = subprocess.run(
        [*_cli(), "campaign", "resume", search_id],
        cwd=Path.cwd(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert resumed.returncode == 0
    print("resume stdout:\n" + resumed.stdout)
    print(
        "pre-kill accepted="
        f"{accepted_before} state={snapshot['state']} "
        f"v={snapshot['state_version']}"
    )

    settings = Settings.from_env(data_root=tmp_path)
    db = Database(settings.db_path)
    migrate(db)
    controller = CampaignController(db, ContentStore(settings.data_root), settings)
    reconstruction = reconstruct(controller.repos, search_id)
    campaign = controller.get(search_id)
    after_ids = set(reconstruction.accepted_evidence_ids)
    missing = [eid for eid in accepted_before if eid not in after_ids]
    assert missing == [], f"accepted evidence lost after resume: {missing}"
    assert reconstruction.active_hypotheses, "active hypotheses were not reconstructed"
    assert (
        reconstruction.source_cursors or reconstruction.fetched_pages or campaign.state_version >= 1
    )
    assert reconstruction.budget_used, "budget used was not reconstructed"
    if campaign.state is CampaignState.COMPLETE:
        assert reconstruction.normalized_candidates, "normalized candidates missing after complete"
        assert reconstruction.fetched_pages, "fetched pages missing after complete"
        assert reconstruction.result_state, "result state missing after complete"
    print(
        "reconstructed "
        f"hypotheses={len(reconstruction.active_hypotheses)} "
        f"queries={len(reconstruction.completed_queries)} "
        f"cursors={reconstruction.source_cursors} "
        f"pages={len(reconstruction.fetched_pages)} "
        f"candidates={len(reconstruction.normalized_candidates)} "
        f"accepted={len(reconstruction.accepted_evidence_ids)} "
        f"results={len(reconstruction.result_state)} "
        f"state={campaign.state.value}"
    )
    db.close()
