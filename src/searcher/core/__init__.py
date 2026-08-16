"""Core primitives: config, ids, time, errors, budgets, capabilities, policy."""

from __future__ import annotations

from searcher.core.budgets import Budget, BudgetUsage, Reservation, SealedBudget
from searcher.core.capabilities import (
    CapabilityName,
    CapabilityProbe,
    CapabilityRecord,
    CapabilityRegistry,
    CapabilityStability,
)
from searcher.core.config import Settings
from searcher.core.errors import (
    BudgetExceeded,
    CrossCampaignAccessError,
    ErrorClass,
    IdempotencyConflict,
    IllegalTransition,
    InvariantViolation,
    NaiveDatetimeError,
    PathEscapeError,
    ReceiptVerificationError,
    SearcherError,
    StaleStateVersion,
    StoragePressureError,
)
from searcher.core.ids import canonical_dumps, idempotency_key, new_id, sha256_hex
from searcher.core.policy import (
    POLICY_VERSION,
    PossiblyRealGate,
    RealGate,
    apply_price_to_authenticity,
    apply_reputation_to_vetoes,
    evaluate_possibly_real_gate,
    evaluate_real_gate,
    route_public_bucket,
)
from searcher.core.time import (
    MonotonicTimer,
    UtcDateTime,
    ensure_utc,
    format_utc,
    parse_utc,
    utc_now,
)

__all__ = [
    "Budget",
    "BudgetExceeded",
    "BudgetUsage",
    "CapabilityName",
    "CapabilityProbe",
    "CapabilityRecord",
    "CapabilityRegistry",
    "CapabilityStability",
    "CrossCampaignAccessError",
    "ErrorClass",
    "IdempotencyConflict",
    "IllegalTransition",
    "InvariantViolation",
    "MonotonicTimer",
    "NaiveDatetimeError",
    "POLICY_VERSION",
    "PathEscapeError",
    "PossiblyRealGate",
    "RealGate",
    "ReceiptVerificationError",
    "Reservation",
    "SealedBudget",
    "SearcherError",
    "Settings",
    "StaleStateVersion",
    "StoragePressureError",
    "UtcDateTime",
    "apply_price_to_authenticity",
    "apply_reputation_to_vetoes",
    "canonical_dumps",
    "ensure_utc",
    "evaluate_possibly_real_gate",
    "evaluate_real_gate",
    "format_utc",
    "idempotency_key",
    "new_id",
    "parse_utc",
    "route_public_bucket",
    "sha256_hex",
    "utc_now",
]
