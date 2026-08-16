"""Job Scraper integration surface. Never imports donor scraper.*."""

from __future__ import annotations

from searcher.integrations.job_scraper.adapter import (
    DiscoveryBatch,
    InProcessJobScraperAdapter,
    NullJobScraperAdapter,
    SourceRunRef,
    SourceRunState,
)
from searcher.integrations.job_scraper.provenance import (
    EXCLUSIONS,
    FREEZE_DATE,
    FROZEN_PATH,
    MANIFEST_DIGEST,
)

__all__ = [
    "DiscoveryBatch",
    "EXCLUSIONS",
    "FREEZE_DATE",
    "FROZEN_PATH",
    "InProcessJobScraperAdapter",
    "MANIFEST_DIGEST",
    "NullJobScraperAdapter",
    "SourceRunRef",
    "SourceRunState",
]
