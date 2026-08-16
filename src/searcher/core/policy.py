"""Policy version and the provisional §20.2 / §20.3 gates as named data."""

from __future__ import annotations

from dataclasses import dataclass, field

from searcher.core.errors import InvariantViolation

POLICY_VERSION = "provisional-1"

# Forbidden labels a fallback/degraded path may never emit (§3.7).
FORBIDDEN_FALLBACK_LABELS = frozenset(
    {
        "REAL",
        "AUTHENTICATED",
        "VERIFIED_GENUINE",
        "EXHAUSTIVE_SEARCH_COMPLETE",
    }
)

ALLOWED_FALLBACK_LABELS = frozenset(
    {
        "CANDIDATE",
        "DIAGNOSTIC",
        "PARTIAL",
        "BLOCKED",
        "UNMEASURABLE",
    }
)


@dataclass(frozen=True, slots=True)
class RealGate:
    """Provisional Real gate. Public promotion reads lower bounds, not means."""

    policy_version: str = POLICY_VERSION
    item_match_lower_bound: float = 0.90
    authenticity_lower_bound: float = 0.80
    evidence_completeness: float = 0.65
    require_live: bool = True
    require_destination_verified: bool = True
    forbid_hard_item_contradiction: bool = True
    forbid_hard_authenticity_contradiction: bool = True
    forbid_scam_signal: bool = True


@dataclass(frozen=True, slots=True)
class PossiblyRealGate:
    policy_version: str = POLICY_VERSION
    require_plausible_item_match: bool = True
    plausible_item_match_lower_bound: float = 0.45
    forbid_hard_exact_model_mismatch: bool = True
    forbid_strong_counterfeit_veto: bool = True


@dataclass(frozen=True, slots=True)
class GateView:
    """Inputs the gates need. Later waves fill this from real evidence."""

    item_match_lower_bound: float
    authenticity_lower_bound: float
    evidence_completeness: float
    availability: str
    live_checked: bool
    destination_verified: bool
    hard_item_contradictions: list[str] = field(default_factory=list)
    hard_authenticity_contradictions: list[str] = field(default_factory=list)
    hard_visual_vetoes: list[str] = field(default_factory=list)
    scam_or_malicious: bool = False
    hard_vetoes: list[str] = field(default_factory=list)


def evaluate_real_gate(view: GateView, gate: RealGate | None = None) -> bool:
    policy = gate or RealGate()
    if view.item_match_lower_bound < policy.item_match_lower_bound:
        return False
    if view.authenticity_lower_bound < policy.authenticity_lower_bound:
        return False
    if view.evidence_completeness < policy.evidence_completeness:
        return False
    if policy.require_live and (view.availability != "LIVE" or not view.live_checked):
        return False
    if policy.require_destination_verified and not view.destination_verified:
        return False
    if policy.forbid_hard_item_contradiction and view.hard_item_contradictions:
        return False
    if policy.forbid_hard_authenticity_contradiction and view.hard_authenticity_contradictions:
        return False
    if policy.forbid_scam_signal and view.scam_or_malicious:
        return False
    return not (view.hard_vetoes or view.hard_visual_vetoes)


def evaluate_possibly_real_gate(view: GateView, gate: PossiblyRealGate | None = None) -> bool:
    policy = gate or PossiblyRealGate()
    if (
        policy.require_plausible_item_match
        and view.item_match_lower_bound < policy.plausible_item_match_lower_bound
    ):
        return False
    if policy.forbid_hard_exact_model_mismatch and view.hard_item_contradictions:
        return False
    if policy.forbid_strong_counterfeit_veto and (
        view.hard_authenticity_contradictions or view.hard_visual_vetoes or view.scam_or_malicious
    ):
        return False
    return not view.hard_vetoes


def route_public_bucket(view: GateView) -> str:
    """Return BucketPublic value. Dead listings and hard vetoes cannot be Real."""
    # GUARD: a candidate with a hard veto cannot enter either public tab.
    if view.hard_vetoes or view.hard_visual_vetoes:
        return "hidden"
    # GUARD: a dead listing cannot become Real. Live check is mandatory for Real.
    if evaluate_real_gate(view):
        return "real"
    if evaluate_possibly_real_gate(view):
        return "possibly_real"
    return "hidden"


def apply_reputation_to_vetoes(
    *,
    hard_visual_vetoes: list[str],
    source_reputation: float,
    public_bucket: str,
) -> str:
    """Source reputation cannot erase a hard visual veto (§32.3 / §3).

    This is the guard. If removed, a high reputation would lift a vetoed
    candidate into a public tab.
    """
    del source_reputation  # reputation is informational only when a veto stands
    if hard_visual_vetoes:
        return "hidden"
    return public_bucket


def apply_price_to_authenticity(
    current_lower_bound: float,
    price_contribution: float,
) -> float:
    """Price may be a weak negative anomaly; it must never raise authenticity.

    This is the guard. If removed, a positive price_contribution would raise
    the authenticity lower bound.
    """
    if price_contribution > 0:
        return current_lower_bound
    return max(0.0, current_lower_bound + price_contribution)


def forbid_fallback_label(label: str) -> str:
    """§3.7: fallback/degraded paths may never emit promoted claims."""
    if label in FORBIDDEN_FALLBACK_LABELS:
        raise InvariantViolation(f"fallback/degraded path may not produce {label}")
    if label not in ALLOWED_FALLBACK_LABELS:
        raise InvariantViolation(f"unknown fallback label: {label}")
    return label
