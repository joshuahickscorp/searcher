"""Shared contract primitives: facts, score intervals, the three judgments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from searcher import SCHEMA_VERSION
from searcher.contracts.enums import (
    Availability,
    DegradedLabel,
    EvidencePolarity,
    FactClass,
    FactOrigin,
    JudgmentKind,
)
from searcher.core.errors import InvariantViolation
from searcher.core.policy import forbid_fallback_label
from searcher.core.time import UtcDateTime


class SearcherModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = SCHEMA_VERSION


class ArtifactRef(SearcherModel):
    digest: str
    media_type: str | None = None


class ClassifiedFact(SearcherModel):
    """A fact-bearing value. Seller origin can never be constructed as OBSERVED."""

    value: str | int | float | bool | None = None
    fact_class: FactClass
    origin: FactOrigin
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def seller_cannot_be_observed(self) -> ClassifiedFact:
        # GUARD: seller text cannot create an OBSERVED fact.
        if self.origin == FactOrigin.SELLER and self.fact_class == FactClass.OBSERVED:
            raise ValueError("seller-reported value cannot be constructed as OBSERVED")
        if self.fact_class == FactClass.REPORTED_BY_SELLER and self.origin not in {
            FactOrigin.SELLER,
            FactOrigin.SOURCE,
        }:
            raise ValueError("REPORTED_BY_SELLER requires a seller or source origin")
        return self


def classified(
    value: str | int | float | bool | None,
    fact_class: FactClass,
    origin: FactOrigin,
    *,
    evidence_refs: list[str] | None = None,
) -> ClassifiedFact:
    return ClassifiedFact(
        value=value,
        fact_class=fact_class,
        origin=origin,
        evidence_refs=evidence_refs or [],
    )


class ScoreInterval(SearcherModel):
    """§19.6: a distribution interval, not a point. Public gates read lower_bound."""

    mean: float
    lower_bound: float
    upper_bound: float

    @model_validator(mode="after")
    def ordered_unit_interval(self) -> ScoreInterval:
        for name in ("mean", "lower_bound", "upper_bound"):
            value = getattr(self, name)
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if not self.lower_bound <= self.mean <= self.upper_bound:
            raise ValueError("require lower_bound <= mean <= upper_bound")
        return self


class ItemMatchJudgment(SearcherModel):
    """ITEM_MATCH only. Cannot be substituted for authenticity or utility."""

    kind: Literal[JudgmentKind.ITEM_MATCH] = JudgmentKind.ITEM_MATCH
    interval: ScoreInterval


class AuthenticityJudgment(SearcherModel):
    """AUTHENTICITY_CONFIDENCE only. Cannot be substituted for match or utility."""

    kind: Literal[JudgmentKind.AUTHENTICITY_CONFIDENCE] = JudgmentKind.AUTHENTICITY_CONFIDENCE
    interval: ScoreInterval
    authority_ceiling: str = "provisional"


class ListingUtilityJudgment(SearcherModel):
    """LISTING_UTILITY only. Cannot be substituted for match or authenticity."""

    kind: Literal[JudgmentKind.LISTING_UTILITY] = JudgmentKind.LISTING_UTILITY
    interval: ScoreInterval
    live: bool = False


class ScoreWithEvidence(SearcherModel):
    interval: ScoreInterval
    support: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    fact_class: FactClass = FactClass.INFERRED
    polarity: EvidencePolarity = EvidencePolarity.SUPPORTING


class PartMatch(SearcherModel):
    part_name: str
    interval: ScoreInterval
    correspondence_ref: str | None = None
    explanation: str | None = None
    fact_class: FactClass = FactClass.INFERRED


class PublicExplanation(SearcherModel):
    """§3.10 fields every displayed record must be able to answer."""

    support: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    live_status: Availability | None = None
    last_checked_at: UtcDateTime | None = None
    compared_images: list[str] = Field(default_factory=list)
    duplicate_image_families: list[str] = Field(default_factory=list)
    seller_reported_fields: list[str] = Field(default_factory=list)


class DegradedOutcome(SearcherModel):
    """Type-level constraint: only §3.7-allowed labels."""

    label: DegradedLabel
    reason: str
    path: Literal["fallback", "degraded"] = "degraded"

    @model_validator(mode="after")
    def not_promoted(self) -> DegradedOutcome:
        forbid_fallback_label(self.label.value)
        return self


def fallback_outcome(label: str, reason: str) -> DegradedOutcome:
    """Construct a degraded outcome. Promoted labels raise."""
    forbid_fallback_label(label)
    return DegradedOutcome(label=DegradedLabel(label), reason=reason)


class EvidenceWeight(SearcherModel):
    """Lightweight evidence used by interval combination guards."""

    evidence_id: str
    family_id: str
    polarity: EvidencePolarity
    weight: float = 0.5
    hard: bool = False


def compute_interval(weights: list[EvidenceWeight]) -> ScoreInterval:
    """Naive interval from remaining evidence. Used by the delete-guard."""
    supporting = [w for w in weights if w.polarity == EvidencePolarity.SUPPORTING]
    contradictory = [w for w in weights if w.polarity == EvidencePolarity.CONTRADICTORY]
    missing = [w for w in weights if w.polarity == EvidencePolarity.MISSING]
    base = 0.0 if not supporting else sum(w.weight for w in supporting) / len(supporting)
    penalty = 0.12 * len(contradictory) + 0.04 * len(missing)
    hard_penalty = 0.25 * sum(1 for w in contradictory if w.hard)
    mean = max(0.0, min(1.0, base - penalty - hard_penalty))
    # Wider interval when evidence is thin or contradictory.
    spread = min(0.45, 0.08 + 0.05 * len(missing) + 0.04 * len(contradictory))
    lower = max(0.0, mean - spread)
    upper = min(1.0, mean + spread * 0.6)
    if lower > mean:
        lower = mean
    if upper < mean:
        upper = mean
    return ScoreInterval(mean=mean, lower_bound=lower, upper_bound=upper)


def lower_bound_after_removal(
    previous: ScoreInterval,
    remaining: list[EvidenceWeight],
) -> ScoreInterval:
    """GUARD: deleting evidence cannot raise a lower confidence bound.

    The raw recompute can rise (e.g. after dropping a contradiction). The
    published lower bound is clamped so cherry-picking cannot inflate it.
    """
    raw = compute_interval(remaining)
    if raw.lower_bound > previous.lower_bound:
        mean = min(raw.mean, previous.mean)
        return ScoreInterval(
            mean=mean,
            lower_bound=previous.lower_bound,
            upper_bound=max(raw.upper_bound, previous.lower_bound, mean),
        )
    return raw


def bucket_confidence(weights: list[EvidenceWeight]) -> float:
    """Scalar used by the hard-contradiction property. Not a public score."""
    interval = compute_interval(weights)
    return interval.lower_bound


def bucket_confidence_after_hard_contradiction(
    previous: float,
    evidence: list[EvidenceWeight],
) -> float:
    """GUARD: adding a hard contradiction cannot raise bucket confidence."""
    raw = bucket_confidence(evidence)
    if any(w.polarity == EvidencePolarity.CONTRADICTORY and w.hard for w in evidence):
        return min(previous, raw)
    return raw


def judgment_kind_of(obj: object) -> JudgmentKind:
    kind = getattr(obj, "kind", None)
    if kind is None:
        raise InvariantViolation("object is not a typed judgment")
    return JudgmentKind(kind)


def as_item_match(judgment: ItemMatchJudgment) -> ItemMatchJudgment:
    if judgment.kind != JudgmentKind.ITEM_MATCH:
        raise InvariantViolation("not an ITEM_MATCH judgment")
    return judgment


def as_authenticity(judgment: AuthenticityJudgment) -> AuthenticityJudgment:
    if judgment.kind != JudgmentKind.AUTHENTICITY_CONFIDENCE:
        raise InvariantViolation("not an AUTHENTICITY_CONFIDENCE judgment")
    return judgment


def as_listing_utility(judgment: ListingUtilityJudgment) -> ListingUtilityJudgment:
    if judgment.kind != JudgmentKind.LISTING_UTILITY:
        raise InvariantViolation("not a LISTING_UTILITY judgment")
    return judgment


def public_gate_reads_lower_bound(judgment: ItemMatchJudgment | AuthenticityJudgment) -> float:
    return judgment.interval.lower_bound


def dump_jsonable(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
