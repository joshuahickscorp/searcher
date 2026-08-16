"""SSE replay of the append-only campaign event log."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from searcher.api.dependencies import get_state, require_campaign
from searcher.api.views import campaign_is_closed, project_sse_data
from searcher.campaigns.events import numbered_public_events

router = APIRouter()

_HEARTBEAT_SECONDS = 15.0
_POLL_SECONDS = 0.15


def _sse(event_id: int, event: str, data: dict[str, object]) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"id: {event_id}\nevent: {event}\ndata: {payload}\n\n".encode()


def _parse_last_event_id(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        return max(0, int(raw.strip()))
    except ValueError:
        return 0


@router.get("/v1/searches/{search_id}/events")
async def stream_events(search_id: str, request: Request) -> StreamingResponse:
    state = get_state(request)
    require_campaign(state, search_id)
    last_id = _parse_last_event_id(request.headers.get("last-event-id"))

    async def generate() -> AsyncIterator[bytes]:
        cursor = last_id
        last_beat = asyncio.get_running_loop().time()
        yield b": connected\n\n"
        while True:
            if await request.is_disconnected():
                return
            if state.controller.repos.is_deleted(search_id):
                return
            batch = numbered_public_events(state.controller.repos, search_id, after=cursor)
            for seq, event in batch:
                yield _sse(seq, event.event_name, project_sse_data(state.controller, event))
                cursor = seq
            closed = campaign_is_closed(state.controller, search_id)
            remaining = numbered_public_events(state.controller.repos, search_id, after=cursor)
            if closed and not remaining:
                return
            now = asyncio.get_running_loop().time()
            if now - last_beat >= _HEARTBEAT_SECONDS:
                yield b": heartbeat\n\n"
                last_beat = now
            await asyncio.sleep(_POLL_SECONDS)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
