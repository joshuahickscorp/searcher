"""Inexpensive broad retrieval (§18.2, §28.1)."""

from __future__ import annotations

from searcher.retrieval.broad import BroadHit, BroadRetrievalResult, retrieve_broad
from searcher.retrieval.cost import (
    CHEAP_STAGES,
    HEAVYWEIGHT_STAGES,
    STAGE_ORDER,
    CostLedger,
    CostStage,
)
from searcher.retrieval.escalation import DEFAULT_BOUNDS, RECALL_FLOOR, EscalationBounds
from searcher.retrieval.pipeline import run_broad_retrieval

__all__ = [
    "CHEAP_STAGES",
    "DEFAULT_BOUNDS",
    "HEAVYWEIGHT_STAGES",
    "RECALL_FLOOR",
    "STAGE_ORDER",
    "BroadHit",
    "BroadRetrievalResult",
    "CostLedger",
    "CostStage",
    "EscalationBounds",
    "retrieve_broad",
    "run_broad_retrieval",
]
