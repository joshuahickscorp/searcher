"""Durable SQLite work frontier. Survives SIGKILL; resume skips terminal keys."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from searcher.contracts.enums import FrontierState, WorkKind
from searcher.core.time import format_utc, utc_now
from searcher.sources.work_key import work_key
from searcher.storage.repositories import Repositories

# §15.2: search → listing → canonical → gallery / declared pagination. Nothing else.
MAX_DEPTH = 3
STALE_INFLIGHT_SECONDS = 30


@dataclass(slots=True)
class FrontierItem:
    run_id: str
    work_key: str
    search_id: str
    source_id: str
    url: str
    kind: WorkKind
    depth: int
    priority: float
    state: FrontierState
    attempts: int = 0
    cursor: str | None = None
    last_error_class: str | None = None
    last_outcome: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "work_key": self.work_key,
            "search_id": self.search_id,
            "source_id": self.source_id,
            "url": self.url,
            "kind": self.kind.value,
            "depth": self.depth,
            "priority": self.priority,
            "state": self.state.value,
            "attempts": self.attempts,
            "cursor": self.cursor,
            "last_error_class": self.last_error_class,
            "last_outcome": self.last_outcome,
            "payload": self.payload,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> FrontierItem:
        payload = row.get("payload_json") or row.get("payload") or {}
        if isinstance(payload, str):
            import json

            payload = json.loads(payload)
        return cls(
            run_id=str(row["run_id"]),
            work_key=str(row["work_key"]),
            search_id=str(row["search_id"]),
            source_id=str(row["source_id"]),
            url=str(row["url"]),
            kind=WorkKind(str(row["kind"])),
            depth=int(row["depth"]),
            priority=float(row["priority"]),
            state=FrontierState(str(row["state"])),
            attempts=int(row.get("attempts") or 0),
            cursor=row.get("cursor"),
            last_error_class=row.get("last_error_class"),
            last_outcome=row.get("last_outcome"),
            payload=dict(payload) if isinstance(payload, dict) else {},
        )


def compute_priority(
    *,
    expected_match_value: float = 0.5,
    coverage_gap: float = 0.3,
    discrimination: float = 0.2,
    novelty: float = 0.4,
    liveness_probability: float = 0.5,
    fetch_cost: float = 0.2,
    duplication_probability: float = 0.1,
    block_probability: float = 0.1,
    policy_risk: float = 0.0,
) -> float:
    """§15.1. Higher is claimed first."""
    return (
        expected_match_value
        + coverage_gap
        + discrimination
        + novelty
        + liveness_probability
        - fetch_cost
        - duplication_probability
        - block_probability
        - policy_risk
    )


class Frontier:
    def __init__(self, repos: Repositories, run_id: str) -> None:
        self.repos = repos
        self.run_id = run_id

    def recover(self) -> int:
        cutoff = format_utc(utc_now() - timedelta(seconds=STALE_INFLIGHT_SECONDS))
        return self.repos.recover_stale_inflight(self.run_id, cutoff)

    def enqueue(
        self,
        *,
        search_id: str,
        source_id: str,
        url: str,
        kind: WorkKind,
        depth: int,
        priority: float | None = None,
        payload: dict[str, Any] | None = None,
        cursor: str | None = None,
    ) -> FrontierItem | None:
        if depth > MAX_DEPTH:
            return None
        if kind is WorkKind.GALLERY and depth > MAX_DEPTH:
            return None
        key = work_key(source_id=source_id, kind=kind.value, target=url)
        existing = self.repos.get_frontier_item(self.run_id, key)
        if existing is not None:
            state = FrontierState(str(existing["state"]))
            # Inhibition of return (§22.4): terminal keys are not retried.
            if state in {FrontierState.DONE, FrontierState.BLOCKED, FrontierState.CANCELLED}:
                return FrontierItem.from_row(existing)
            if state is FrontierState.INFLIGHT:
                return FrontierItem.from_row(existing)
        item = FrontierItem(
            run_id=self.run_id,
            work_key=key,
            search_id=search_id,
            source_id=source_id,
            url=url,
            kind=kind,
            depth=depth,
            priority=priority if priority is not None else compute_priority(),
            state=FrontierState.PENDING,
            payload=payload or {},
            cursor=cursor,
        )
        self.repos.upsert_frontier_item(item.to_row())
        return item

    def pop(self, limit: int = 1) -> list[FrontierItem]:
        rows = self.repos.pop_frontier_batch(self.run_id, limit)
        return [FrontierItem.from_row(row) for row in rows]

    def complete(
        self,
        item: FrontierItem,
        *,
        outcome: str,
        error_class: str | None = None,
        state: FrontierState = FrontierState.DONE,
        cursor: str | None = None,
    ) -> None:
        item.state = state
        item.last_outcome = outcome
        item.last_error_class = error_class
        if cursor is not None:
            item.cursor = cursor
        self.repos.upsert_frontier_item(item.to_row())

    def get(self, key: str) -> FrontierItem | None:
        row = self.repos.get_frontier_item(self.run_id, key)
        return FrontierItem.from_row(row) if row else None

    def pending_count(self) -> int:
        return len(self.repos.list_frontier(self.run_id, state=FrontierState.PENDING.value))

    def list_all(self) -> list[FrontierItem]:
        return [FrontierItem.from_row(row) for row in self.repos.list_frontier(self.run_id)]
