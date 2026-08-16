"""Belief construction and updates. History is append-only."""

from __future__ import annotations

from searcher.contracts.enums import FactClass, FactOrigin
from searcher.contracts.models import Belief, BeliefUpdate
from searcher.core.time import utc_now


def make_belief(
    value: str | None,
    *,
    confidence: float,
    fact_class: FactClass,
    origin: FactOrigin,
    evidence: list[str] | None = None,
    families: int = 0,
) -> Belief:
    return Belief(
        value=value,
        confidence=max(0.0, min(1.0, confidence)),
        fact_class=fact_class,
        origin=origin,
        evidence=list(evidence or []),
        independent_source_families=families,
        update_history=[],
    )


def empty_belief() -> Belief:
    return make_belief(
        None, confidence=0.0, fact_class=FactClass.UNRESOLVED, origin=FactOrigin.SYSTEM
    )


def update_belief(
    belief: Belief,
    *,
    value: str | None,
    confidence: float,
    fact_class: FactClass,
    origin: FactOrigin,
    reason: str,
    evidence_ref: str | None = None,
    families: int | None = None,
) -> Belief:
    history = list(belief.update_history)
    history.append(
        BeliefUpdate(
            at=utc_now(),
            previous_value=belief.value,
            new_value=value,
            reason=reason,
            evidence_ref=evidence_ref,
        )
    )
    evidence = list(belief.evidence)
    if evidence_ref and evidence_ref not in evidence:
        evidence.append(evidence_ref)
    return belief.model_copy(
        update={
            "value": value,
            "confidence": max(0.0, min(1.0, confidence)),
            "fact_class": fact_class,
            "origin": origin,
            "evidence": evidence,
            "independent_source_families": (
                families if families is not None else belief.independent_source_families
            ),
            "update_history": history,
        }
    )


def lower_confidence(belief: Belief, *, reason: str, floor: float = 0.05) -> Belief:
    return update_belief(
        belief,
        value=belief.value,
        confidence=max(floor, belief.confidence * 0.55),
        fact_class=FactClass.CONTRADICTED
        if belief.fact_class is not FactClass.UNRESOLVED
        else belief.fact_class,
        origin=belief.origin,
        reason=reason,
    )
