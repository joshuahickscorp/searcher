"""Cheap liveness. No model load, no browser, no donor import."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from searcher.api.dependencies import get_state
from searcher.core.time import format_utc, utc_now

router = APIRouter()


@router.get("/v1/health")
def get_health(request: Request) -> dict[str, Any]:
    """API up vs lane blocked. Unreachable is a failed fetch, not this body."""
    state = get_state(request)
    state.db.execute("SELECT 1").fetchone()
    index_ok = True
    index_entries = 0
    index_reason = ""
    try:
        index_entries = int(
            state.db.execute("SELECT COUNT(*) AS n FROM index_listings").fetchone()["n"]
        )
    except Exception as exc:
        index_ok = False
        index_reason = type(exc).__name__
    lanes: dict[str, dict[str, Any]] = {
        "storage": {"ok": True},
        "index": {"ok": index_ok, "entries": index_entries},
        "discovery": {
            "ok": True,
            "reason": "sources layer present; live discovery is started by the campaign runner",
        },
        "vision": {
            "ok": True,
            "reason": "not probed on /v1/health; see GET /v1/capabilities",
        },
    }
    if not index_ok:
        lanes["index"]["reason"] = index_reason
    blocked = [
        {"name": name, "reason": str(lane.get("reason") or "blocked")}
        for name, lane in lanes.items()
        if not lane.get("ok")
    ]
    status = "degraded" if blocked else "ok"
    return {
        "status": status,
        "api": "up",
        "db": "ok",
        "checked_at": format_utc(utc_now()),
        "lanes": lanes,
        "blocked_lanes": blocked,
    }
