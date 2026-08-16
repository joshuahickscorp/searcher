"""SIGKILL mid-pipeline (after discovery), then resume without losing evidence."""

from __future__ import annotations

import os
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

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

MID = {
    CampaignState.NORMALIZING.value,
    CampaignState.DEDUPLICATING.value,
    CampaignState.BROAD_RETRIEVAL.value,
    CampaignState.FINE_MATCHING.value,
    CampaignState.AUTHENTICITY_REVIEW.value,
    CampaignState.LIVE_CHECKING.value,
    CampaignState.RANKING.value,
}


def _poll(db_path: Path) -> dict[str, object]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        campaign = conn.execute("SELECT * FROM campaigns").fetchone()
        if campaign is None:
            return {"ready": False}
        state = campaign["state"]
        evidence = conn.execute(
            "SELECT evidence_id FROM evidence_metadata WHERE search_id = ? AND accepted = 1",
            (campaign["search_id"],),
        ).fetchall()
        candidates = conn.execute(
            "SELECT COUNT(*) AS n FROM candidates WHERE search_id = ?",
            (campaign["search_id"],),
        ).fetchone()["n"]
        mid = state in MID or (state == CampaignState.ACQUIRING.value and candidates >= 1)
        return {
            "ready": bool(mid) and (len(evidence) >= 1 or candidates >= 1),
            "state": state,
            "state_version": campaign["state_version"],
            "accepted_ids": [row["evidence_id"] for row in evidence],
            "candidates": candidates,
            "search_id": campaign["search_id"],
        }
    except sqlite3.OperationalError:
        return {"ready": False}
    finally:
        conn.close()


HELPER = r"""
import os
from searcher.campaigns.controller import CampaignController
from searcher.campaigns.orchestrator import CampaignOrchestrator
from searcher.core.config import Settings
from searcher.evidence.content_store import ContentStore
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate
from searcher.workers.api_campaign import create_api_campaign
from tests.support.offline_shop import (
    install_offline_adapter,
    start_shop,
    tiny_png,
)

os.environ["SEARCHER_ALLOW_LOOPBACK"] = "1"
httpd, base = start_shop()
install_offline_adapter(base)
settings = Settings.from_env()
settings.ensure_data_root()
db = Database(settings.db_path)
migrate(db)
store = ContentStore(settings.data_root)
controller = CampaignController(db, store, settings)
search_id = create_api_campaign(
    controller,
    uploads=[(tiny_png(), "ref.png")],
    text="Archive Alpha Trainer 2007",
    tags=["archive"],
    client_search_id=None,
    settings=settings,
)
print("search_id:" + search_id, flush=True)
orch = CampaignOrchestrator(controller, source_names=["offline_shop"], max_rounds=1)
orch.run(search_id)
"""


@pytest.mark.timeout(120)
def test_sigkill_mid_pipeline_then_resume(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["SEARCHER_DATA_ROOT"] = str(tmp_path)
    env["SEARCHER_STEP_DELAY_MS"] = "400"
    env["SEARCHER_LIVE_DISCOVERY"] = "1"
    env["SEARCHER_ALLOW_LOOPBACK"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(Path.cwd())
    helper = tmp_path / "run_orch.py"
    helper.write_text(HELPER, encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(helper)],
        cwd=Path.cwd(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    snapshot: dict[str, object] | None = None
    deadline = time.time() + 50
    db_path = tmp_path / "searcher.sqlite"
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                out, err = proc.communicate()
                raise AssertionError(
                    f"orchestrator finished before SIGKILL (code={proc.returncode})\n{out}\n{err}"
                )
            status = _poll(db_path)
            if status.get("ready") and status.get("state") not in TERMINAL:
                snapshot = status
                break
            time.sleep(0.05)
        if snapshot is None:
            proc.kill()
            out, err = proc.communicate()
            raise AssertionError(f"timed out waiting for mid-pipeline state\n{out}\n{err}")
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    assert snapshot is not None
    accepted_before = list(snapshot["accepted_ids"])  # type: ignore[arg-type]
    assert accepted_before
    assert snapshot["state"] not in TERMINAL
    search_id = str(snapshot["search_id"])

    env.pop("SEARCHER_STEP_DELAY_MS", None)
    resumed = subprocess.run(
        [sys.executable, "-m", "searcher", "campaign", "resume", search_id],
        cwd=Path.cwd(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert resumed.returncode == 0
    settings = Settings.from_env(data_root=tmp_path)
    db = Database(settings.db_path)
    migrate(db)
    controller = CampaignController(db, ContentStore(settings.data_root), settings)
    reconstruction = reconstruct(controller.repos, search_id)
    after = set(reconstruction.accepted_evidence_ids)
    missing = [eid for eid in accepted_before if eid not in after]
    assert missing == [], f"accepted evidence lost: {missing}"
    campaign = controller.get(search_id)
    assert campaign.state.value in TERMINAL or reconstruction.normalized_candidates
    db.close()
