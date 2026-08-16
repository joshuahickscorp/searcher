"""Result list and detail. Never invents a bucket the engine did not store."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from searcher.api.dependencies import ApiError, get_state, require_campaign
from searcher.api.views import list_public_results, project_stored_result
from searcher.contracts.enums import BucketPublic

router = APIRouter()


@router.get("/v1/searches/{search_id}/results")
def list_results(
    search_id: str,
    request: Request,
    bucket: str | None = Query(default=None),
) -> dict[str, Any]:
    state = get_state(request)
    require_campaign(state, search_id)
    if bucket is not None and bucket not in {
        BucketPublic.REAL.value,
        BucketPublic.POSSIBLY_REAL.value,
        BucketPublic.REPLICA.value,
    }:
        raise ApiError(400, "bad_bucket", "bucket must be real, possibly_real, or replica.")
    return list_public_results(state.controller, search_id, bucket)


@router.get("/v1/results/{result_id}")
def get_result(result_id: str, request: Request) -> dict[str, Any]:
    state = get_state(request)
    row = state.controller.repos.get_result_row(result_id)
    if row is None or state.controller.repos.is_deleted(str(row["search_id"])):
        raise ApiError(404, "result_not_found", "This result is no longer available.")
    return project_stored_result(state.controller, row, rank=1)
