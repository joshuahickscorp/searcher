"""§17.7 duplicate-first savings record."""

from __future__ import annotations

from searcher.deduplication.clusters import DedupeResult


def savings_record(result: DedupeResult) -> dict[str, int]:
    return dict(result.savings)
