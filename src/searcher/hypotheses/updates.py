"""Portfolio updates. Weak hypotheses are archived, not deleted."""

from __future__ import annotations

from searcher.contracts.enums import HypothesisStatus
from searcher.contracts.models import ItemHypothesis


def archive_weak(
    hypotheses: list[ItemHypothesis], *, ceiling: int = 8, floor: float = 0.03
) -> list[ItemHypothesis]:
    active = [h for h in hypotheses if h.status is HypothesisStatus.ACTIVE]
    others = [h for h in hypotheses if h.status is not HypothesisStatus.ACTIVE]
    active.sort(key=lambda h: h.posterior, reverse=True)
    kept: list[ItemHypothesis] = []
    archived: list[ItemHypothesis] = []
    for index, hyp in enumerate(active):
        if index >= ceiling or hyp.posterior < floor:
            archived.append(hyp.model_copy(update={"status": HypothesisStatus.ARCHIVED}))
        else:
            kept.append(hyp)
    # Never drop archived records.
    return kept + archived + others


def bound_portfolio(hypotheses: list[ItemHypothesis], *, ceiling: int = 8) -> list[ItemHypothesis]:
    return archive_weak(hypotheses, ceiling=ceiling)
