"""Warm local index of public listing work. Cache of work, never a truth-gate shortcut."""

from __future__ import annotations

from searcher.index.consult import consult_and_surface, remember_campaign
from searcher.index.keys import CacheVersions, cache_key, versions_from_settings
from searcher.index.liveness import apply_liveness_ttl, liveness_expired, present_availability
from searcher.index.store import IndexEvidence, IndexHit, WarmIndex, hypothesis_digest

__all__ = [
    "CacheVersions",
    "IndexEvidence",
    "IndexHit",
    "WarmIndex",
    "apply_liveness_ttl",
    "cache_key",
    "consult_and_surface",
    "hypothesis_digest",
    "liveness_expired",
    "present_availability",
    "remember_campaign",
    "versions_from_settings",
]
