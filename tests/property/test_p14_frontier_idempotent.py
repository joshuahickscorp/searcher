"""Frontier work keys are idempotent."""

from __future__ import annotations

from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import FrontierState, WorkKind
from searcher.core.config import Settings
from searcher.sources.frontier import Frontier
from searcher.sources.work_key import work_key
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate
from searcher.storage.repositories import Repositories


@given(st.sampled_from(["a", "a?utm_source=x", "a?fbclid=1"]))
def test_work_key_collapses_tracking(suffix: str) -> None:
    left = work_key(
        source_id="kind", kind="listing", target="https://shop.example/products/" + suffix
    )  # noqa: E501
    right = work_key(source_id="kind", kind="listing", target="https://shop.example/products/a")
    assert left == right


def test_enqueue_same_key_is_one_row(tmp_path: Path) -> None:
    settings = Settings.from_env(data_root=tmp_path)
    settings.ensure_data_root()
    db = Database(settings.db_path)
    migrate(db)
    repos = Repositories(db)
    frontier = Frontier(repos, "run-1")
    first = frontier.enqueue(
        search_id="s",
        source_id="kind",
        url="https://shop.example/products/a?utm_source=x",
        kind=WorkKind.LISTING,
        depth=1,
    )
    second = frontier.enqueue(
        search_id="s",
        source_id="kind",
        url="https://shop.example/products/a",
        kind=WorkKind.LISTING,
        depth=1,
    )
    assert first is not None and second is not None
    assert first.work_key == second.work_key
    assert len(repos.list_frontier("run-1")) == 1
    frontier.complete(first, outcome="SEARCHED_MATCHES_FOUND", state=FrontierState.DONE)
    third = frontier.enqueue(
        search_id="s",
        source_id="kind",
        url="https://shop.example/products/a",
        kind=WorkKind.LISTING,
        depth=1,
    )
    assert third is not None
    assert third.state is FrontierState.DONE
    db.close()
