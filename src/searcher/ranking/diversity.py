"""§21.5 diversity-aware ordering. Never overrides bucket safety."""

from __future__ import annotations

from searcher.contracts.enums import BucketPublic
from searcher.ranking.order import RankedResult


def diversify(
    rows: list[RankedResult],
    *,
    family_of: dict[str, str],
    public: BucketPublic,
) -> list[RankedResult]:
    """Prefer unseen image/seller families, but keep all items inside their tab."""
    del public
    seen: set[str] = set()
    preferred: list[RankedResult] = []
    deferred: list[RankedResult] = []
    for row in rows:
        family = family_of.get(row.decision.candidate_id, row.decision.candidate_id)
        if family in seen:
            deferred.append(row)
        else:
            seen.add(family)
            preferred.append(row)
    return preferred + deferred
