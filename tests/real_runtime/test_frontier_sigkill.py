"""SIGKILL mid source-run: completed frontier keys are not redone."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from searcher.contracts.enums import FrontierState, WorkKind
from searcher.core.config import Settings
from searcher.sources.frontier import Frontier
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate
from searcher.storage.repositories import Repositories


@pytest.mark.timeout(60)
def test_sigkill_frontier_resume(tmp_path: Path) -> None:
    settings = Settings.from_env(data_root=tmp_path)
    settings.ensure_data_root()
    db = Database(settings.db_path)
    migrate(db)
    repos = Repositories(db)
    frontier = Frontier(repos, "run-kill")
    a = frontier.enqueue(
        search_id="s",
        source_id="kind",
        url="https://example.com/a",
        kind=WorkKind.LISTING,
        depth=1,
    )
    b = frontier.enqueue(
        search_id="s",
        source_id="kind",
        url="https://example.com/b",
        kind=WorkKind.LISTING,
        depth=1,
    )
    assert a is not None and b is not None
    frontier.complete(a, outcome="SEARCHED_MATCHES_FOUND", state=FrontierState.DONE)
    db.close()

    child = r"""
import os, time, sys
from pathlib import Path
from searcher.core.config import Settings
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate
from searcher.storage.repositories import Repositories
from searcher.sources.frontier import Frontier
from searcher.contracts.enums import FrontierState

settings = Settings.from_env()
db = Database(settings.db_path)
migrate(db)
repos = Repositories(db)
frontier = Frontier(repos, "run-kill")
# Simulate work on B then die before commit.
time.sleep(2)
print("would_complete_b", flush=True)
time.sleep(30)
"""
    env = os.environ.copy()
    env["SEARCHER_DATA_ROOT"] = str(tmp_path)
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-c", child],
        cwd=Path.cwd(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(0.4)
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=5)

    db = Database(settings.db_path)
    migrate(db)
    repos = Repositories(db)
    frontier = Frontier(repos, "run-kill")
    recovered = frontier.recover()
    item_a = frontier.get(a.work_key)
    item_b = frontier.get(b.work_key)
    assert item_a is not None and item_a.state is FrontierState.DONE
    assert item_b is not None
    assert item_b.state in {FrontierState.PENDING, FrontierState.INFLIGHT}
    if item_b.state is FrontierState.INFLIGHT:
        frontier.recover()
        item_b = frontier.get(b.work_key)
        assert item_b is not None
        assert item_b.state is FrontierState.PENDING
    # Resume does not refetch A.
    popped = frontier.pop(2)
    keys = {item.work_key for item in popped}
    assert a.work_key not in keys
    assert b.work_key in keys
    print(
        json.dumps(
            {
                "accepted_before": [a.work_key],
                "recovered_inflight": recovered,
                "popped": list(keys),
            }
        )
    )
    db.close()
