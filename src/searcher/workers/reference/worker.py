"""Reference worker capsule. Importing this module does not start a process."""

from __future__ import annotations

from pathlib import Path

from searcher.campaigns.controller import CampaignController
from searcher.core.config import Settings
from searcher.workers.reference.pipeline import run_reference_query_wave


def run(
    controller: CampaignController,
    search_id: str,
    image_paths: list[Path],
    *,
    settings: Settings | None = None,
) -> dict[str, object]:
    return run_reference_query_wave(controller, search_id, image_paths, settings=settings)
