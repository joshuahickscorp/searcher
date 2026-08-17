"""§26.9 capabilities. Reflects the real probe; does not invent lanes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from searcher.api.dependencies import get_state
from searcher.campaigns.orchestrator import layers_present
from searcher.integrations.visionmcp.probe import donor_status, probe_capabilities

router = APIRouter()

_ACCEPTED = ("image/jpeg", "image/png", "image/webp", "image/gif")


def _lane(*, enabled: bool, present: bool, missing: str, disabled: str) -> dict[str, object]:
    if not present:
        return {"available": False, "reason": missing}
    if not enabled:
        return {"available": False, "reason": disabled}
    return {"available": True, "reason": ""}


def _with_searcher_own(lane: dict[str, Any]) -> dict[str, Any]:
    """Report what this project can do, not only what the donor lacks.

    The probe describes the pinned donor. For LOCAL_CORRESPONDENCE that note
    read "No SIFT/SuperPoint/LoFTR" while Searcher's own ORB detector was
    answering, so the endpoint denied a capability the product was using. A lane
    the product implements itself is reported on its own terms.
    """
    if lane.get("name") != "LOCAL_CORRESPONDENCE":
        return lane
    from searcher.matching.features import opencv_available

    if not opencv_available():
        lane["notes"] = (
            "opencv is absent, so correspondence falls back to a descriptor that "
            "cannot separate two objects. Install the correspondence extra."
        )
        return lane
    lane["available"] = True
    lane["stability"] = "experimental"
    lane["dependency"] = "opencv"
    lane["authority_ceiling"] = "OBSERVED-pixels"
    lane["notes"] = (
        "Searcher's own ORB detector with ratio test and RANSAC homography. "
        "Not the donor's; the donor has no correspondence at the pinned SHA."
    )
    return lane


@router.get("/v1/capabilities")
def get_capabilities(request: Request) -> dict[str, Any]:
    state = get_state(request)
    report = probe_capabilities()
    lanes = [_with_searcher_own(record.model_dump(mode="json")) for record in report.capabilities]
    # Derived from the same list the caller sees. Reading the raw probe here
    # while lanes carried Searcher's own capability let one payload say a lane
    # was both available and blocked.
    blocked = [
        {"name": lane["name"], "reason": lane.get("notes")}
        for lane in lanes
        if not lane.get("available")
    ]
    return {
        "api_version": "v1",
        "max_images": state.settings.max_images_per_search,
        "min_images": 1,
        "accepted_media_types": list(_ACCEPTED),
        "lanes": lanes,
        "blocked_lanes": blocked,
        "donor": donor_status(),
        "discovery": _lane(
            enabled=state.settings.live_discovery,
            present=layers_present()["discovery"],
            missing="The sources/discovery layer is not present in this process.",
            disabled="Live listing discovery is disabled in this process.",
        ),
        "routing": _lane(
            enabled=state.settings.live_discovery,
            present=layers_present()["routing"],
            missing=(
                "Retrieval, matching, authenticity, and ranking are not present in this process."
            ),
            disabled="Result routing is disabled in this process.",
        ),
        "schema_version": report.schema_version,
    }
