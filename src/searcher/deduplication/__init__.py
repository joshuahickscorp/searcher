"""§17 deduplication and clustering."""

from __future__ import annotations

from searcher.deduplication.clusters import DedupeResult, cluster_candidates
from searcher.deduplication.images import content_fingerprint, image_family_id
from searcher.deduplication.savings import savings_record
from searcher.deduplication.urls import url_cluster_key

__all__ = [
    "DedupeResult",
    "cluster_candidates",
    "content_fingerprint",
    "image_family_id",
    "savings_record",
    "url_cluster_key",
]
