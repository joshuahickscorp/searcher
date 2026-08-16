"""§26.9 capabilities. Reflects the real probe; does not invent lanes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from searcher.api.dependencies import get_state
from searcher.integrations.visionmcp.probe import donor_status, probe_capabilities

router = APIRouter()

_ACCEPTED = ("image/jpeg", "image/png", "image/webp", "image/gif")


@router.get("/v1/capabilities")
def get_capabilities(request: Request) -> dict[str, Any]:
    state = get_state(request)
    report = probe_capabilities()
    lanes = [record.model_dump(mode="json") for record in report.capabilities]
    blocked = [
        {"name": record.name.value, "reason": record.notes}
        for record in report.capabilities
        if not record.available
    ]
    return {
        "api_version": "v1",
        "max_images": state.settings.max_images_per_search,
        "min_images": 1,
        "accepted_media_types": list(_ACCEPTED),
        "lanes": lanes,
        "blocked_lanes": blocked,
        "donor": donor_status(),
        "discovery": {
            "available": False,
            "reason": "The sources/discovery layer is not present in this process.",
        },
        "routing": {
            "available": False,
            "reason": (
                "Retrieval, matching, authenticity, and ranking are not present in this process."
            ),
        },
        "schema_version": report.schema_version,
    }
