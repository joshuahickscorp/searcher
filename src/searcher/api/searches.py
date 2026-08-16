"""Search create, read, refresh, and cancel."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from searcher.api.dependencies import (
    ApiError,
    get_state,
    require_campaign,
    start_campaign_thread,
    wait_for_campaign,
)
from searcher.api.uploads import parse_create_form
from searcher.api.views import create_body, project_search
from searcher.campaigns.states import is_terminal
from searcher.contracts.enums import PublicEventName
from searcher.receipts.types import LiveCheckReceipt
from searcher.workers.api_campaign import create_api_campaign

router = APIRouter()


@router.post("/v1/searches")
async def create_search(request: Request) -> JSONResponse:
    state = get_state(request)
    content_type = (request.headers.get("content-type") or "").lower()
    if not content_type.startswith("multipart/form-data"):
        raise ApiError(
            415,
            "expected_multipart",
            "POST /v1/searches expects multipart/form-data.",
        )
    parsed = await parse_create_form(await request.form(), state.settings)
    if parsed.client_search_id:
        existing = state.controller.find_by_client_search_id(parsed.client_search_id)
        if existing is not None:
            return JSONResponse(
                create_body(existing.search_id, existing.state.value),
                status_code=200,
            )
    search_id = create_api_campaign(
        state.controller,
        uploads=parsed.uploads,
        text=parsed.text,
        tags=parsed.tags,
        client_search_id=parsed.client_search_id,
        settings=state.settings,
    )
    campaign = state.controller.get(search_id)
    if not is_terminal(campaign.state):
        start_campaign_thread(state, search_id)
    return JSONResponse(create_body(search_id, campaign.state.value), status_code=201)


@router.get("/v1/searches/{search_id}")
def get_search(search_id: str, request: Request) -> dict[str, Any]:
    state = get_state(request)
    campaign = require_campaign(state, search_id)
    return project_search(state.controller, campaign)


@router.post("/v1/searches/{search_id}/cancel")
def cancel_search(search_id: str, request: Request) -> dict[str, Any]:
    state = get_state(request)
    require_campaign(state, search_id)
    campaign = state.controller.cancel(search_id)
    wait_for_campaign(state, search_id, timeout=1.0)
    campaign = state.controller.get(search_id)
    return project_search(state.controller, campaign)


@router.post("/v1/searches/{search_id}/refresh")
def refresh_search(search_id: str, request: Request) -> JSONResponse:
    state = get_state(request)
    campaign = require_campaign(state, search_id)
    results = state.controller.repos.list_results(search_id)
    if not results:
        reason = (
            "No stored listing can be refreshed. Live re-verification is unavailable "
            "because the discovery layer is not present."
        )
        refreshed = False
    else:
        reason = (
            "Live re-verification of availability, price, size, and destination did not run. "
            "The API does not fetch listing URLs; that work belongs to the sources layer."
        )
        refreshed = False
    state.controller.emit(
        search_id,
        PublicEventName.SEARCH_WARNING.value,
        payload={"code": "refresh_unavailable", "message": reason},
        actor="api",
    )
    receipt = LiveCheckReceipt(
        search_id=search_id,
        result_ids=[str(row["result_id"]) for row in results],
        refreshed=refreshed,
        reason=reason,
    ).seal()
    state.controller.store_receipt(receipt)
    body = project_search(state.controller, campaign)
    body["refreshed"] = refreshed
    body["refresh_reason"] = reason
    return JSONResponse(body, status_code=202)
