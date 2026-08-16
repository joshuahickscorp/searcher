"""§27.4 / §29.6 campaign deletion."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from searcher.api.dependencies import get_state, require_campaign, wait_for_campaign

router = APIRouter()


@router.delete("/v1/searches/{search_id}", status_code=204)
def delete_search(search_id: str, request: Request) -> Response:
    state = get_state(request)
    require_campaign(state, search_id)
    state.controller.cancellation.request(search_id)
    wait_for_campaign(state, search_id, timeout=2.0)
    state.controller.delete(search_id)
    return Response(status_code=204)
