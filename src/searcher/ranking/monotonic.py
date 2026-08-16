"""§21.4 monotonic constraints. Executable guards, not comments."""

from __future__ import annotations

from searcher.contracts.enums import EvidencePolarity
from searcher.contracts.primitives import (
    EvidenceWeight,
    ScoreInterval,
    bucket_confidence_after_hard_contradiction,
    compute_interval,
    lower_bound_after_removal,
)
from searcher.core.policy import apply_price_to_authenticity, apply_reputation_to_vetoes
from searcher.evidence.independence import independent_family_count
from searcher.evidence.records import EvidenceRecord


def independence_after_duplicate(records: list[EvidenceRecord]) -> int:
    return independent_family_count(records)


def after_hard_contradiction(previous: float, evidence: list[EvidenceWeight]) -> float:
    return bucket_confidence_after_hard_contradiction(previous, evidence)


def after_removal(previous: ScoreInterval, remaining: list[EvidenceWeight]) -> ScoreInterval:
    return lower_bound_after_removal(previous, remaining)


def authenticity_after_price(current_lower: float, price_contribution: float) -> float:
    return apply_price_to_authenticity(current_lower, price_contribution)


def bucket_after_reputation(hard_visual_vetoes: list[str], reputation: float, bucket: str) -> str:
    return apply_reputation_to_vetoes(
        hard_visual_vetoes=hard_visual_vetoes,
        source_reputation=reputation,
        public_bucket=bucket,
    )


def user_text_cannot_override(hard_visual: list[str], user_agrees: bool, bucket: str) -> str:
    del user_agrees
    if hard_visual:
        return "hidden"
    return bucket


def badge_cannot_override(hard_physical: list[str], platform_badge: bool, bucket: str) -> str:
    del platform_badge
    if hard_physical:
        return "hidden"
    return bucket


def interval_with_duplicate_family(
    existing: list[EvidenceWeight], extra: EvidenceWeight
) -> ScoreInterval:
    """Adding a duplicate family member does not raise the published interval."""
    previous = compute_interval(existing)
    # Duplicate polarity contributes nothing.
    if extra.polarity is EvidencePolarity.DUPLICATE:
        return previous
    same_family = any(item.family_id == extra.family_id for item in existing)
    if same_family:
        return previous
    updated = compute_interval(existing + [extra])
    if updated.lower_bound > previous.lower_bound and extra.polarity is EvidencePolarity.SUPPORTING:
        # Independent new support may raise; duplicates must not reach here.
        return updated
    return updated
