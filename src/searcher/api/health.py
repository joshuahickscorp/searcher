"""Cheap liveness. No model load, no browser, no donor import."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from searcher.api.dependencies import get_state

router = APIRouter()


@router.get("/v1/health")
def get_health(request: Request) -> dict[str, Any]:
    state = get_state(request)
    state.db.execute("SELECT 1").fetchone()
    return {"status": "ok"}
