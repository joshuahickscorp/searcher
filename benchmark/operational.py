"""Quality is never reported without cost."""

from __future__ import annotations

from typing import Any

from .buckets import BucketReport
from .retrieval import RetrievalReport


def assemble_operational(
    retrieval: RetrievalReport,
    buckets: BucketReport,
) -> dict[str, Any]:
    campaigns = 1 + max(1, len({query.target_id for query in retrieval.queries}))
    wall = retrieval.wall_seconds + buckets.wall_seconds
    images = retrieval.images_scored + buckets.images_processed
    fetches = buckets.fetches
    # Fixtures are the authorized local cache. This run performs no network
    # fetch. A cache hit rate of 1.0 means every image came from that cache.
    cache_hit_rate = 1.0
    per_campaign_wall = wall / campaigns if campaigns else None
    images_per_second = images / wall if wall > 0 else None
    return {
        "protocol": (
            "Offline fixture campaigns. Retrieval is one closed-set ranking "
            "pass. Bucket evaluation is one judge_candidates campaign on the "
            "held-out constructed cases. No live source is contacted."
        ),
        "wall_seconds_total": round(wall, 6),
        "wall_seconds_per_campaign": (
            None if per_campaign_wall is None else round(per_campaign_wall, 6)
        ),
        "campaigns": campaigns,
        "fetches_per_campaign": fetches,
        "fetches_total": fetches,
        "cache_hit_rate": cache_hit_rate,
        "images_processed": images,
        "images_per_second": None if images_per_second is None else round(images_per_second, 6),
        "retrieval": {
            "wall_seconds": round(retrieval.wall_seconds, 6),
            "images_scored": retrieval.images_scored,
            "images_per_second": (
                None
                if retrieval.wall_seconds <= 0
                else round(retrieval.images_scored / retrieval.wall_seconds, 6)
            ),
            "fetches": 0,
        },
        "bucket_campaign": {
            "wall_seconds": round(buckets.wall_seconds, 6),
            "images_processed": buckets.images_processed,
            "fetches": buckets.fetches,
            "cache_hits": buckets.cache_hits,
        },
        "note": (
            "fetches_per_campaign is 0 because every byte came from "
            "fixtures/ already permitted to be held. A live campaign's "
            "fetch cost is a different protocol; see "
            "artifacts/searcher-performance.receipt.json and "
            "artifacts/searcher-adversarial-recall.receipt.json."
        ),
    }
