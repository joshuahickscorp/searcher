"""§12.3 alias promotion. One low-confidence seller title can never rewrite identity."""

from __future__ import annotations

from dataclasses import dataclass

from searcher.contracts.enums import FactClass, FactOrigin
from searcher.contracts.models import AliasBelief
from searcher.hypotheses.beliefs import make_belief

HIGH_AUTHORITY_FAMILIES = frozenset(
    {
        "catalog",
        "manufacturer",
        "museum",
        "lookbook",
        "wikipedia",
        "house_archive",
    }
)


@dataclass(frozen=True, slots=True)
class AliasEvidence:
    alias: str
    source_family: str
    authority: str
    confidence: float
    retrieval_improved: bool = False
    visual_verification_passed: bool = False
    language: str | None = None


def can_promote_alias(evidence: list[AliasEvidence]) -> bool:
    """Promotion requires one high-authority source, two families, or verified retrieval."""
    if not evidence:
        return False
    high = any(
        item.authority in HIGH_AUTHORITY_FAMILIES and item.confidence >= 0.6 for item in evidence
    )
    if high:
        return True
    families = {item.source_family for item in evidence if item.confidence >= 0.4}
    if len(families) >= 2:
        return True
    return any(item.retrieval_improved and item.visual_verification_passed for item in evidence)


def seller_title_alone_cannot_promote(evidence: list[AliasEvidence]) -> bool:
    """True when the only evidence is a single low-confidence seller title."""
    if len(evidence) != 1:
        return False
    item = evidence[0]
    return (
        item.source_family in {"seller", "listing", "marketplace"}
        and item.authority not in HIGH_AUTHORITY_FAMILIES
        and item.confidence < 0.6
        and not (item.retrieval_improved and item.visual_verification_passed)
    )


def promote_or_hold(evidence: list[AliasEvidence]) -> AliasBelief | None:
    if not evidence:
        return None
    alias = evidence[0].alias.strip()
    if not alias:
        return None
    if seller_title_alone_cannot_promote(evidence) or not can_promote_alias(evidence):
        return AliasBelief(
            alias=alias,
            language=evidence[0].language,
            belief=make_belief(
                alias,
                confidence=min(item.confidence for item in evidence) * 0.4,
                fact_class=FactClass.REPORTED_BY_SELLER
                if evidence[0].source_family in {"seller", "listing"}
                else FactClass.INFERRED,
                origin=FactOrigin.SELLER
                if evidence[0].source_family in {"seller", "listing"}
                else FactOrigin.INFERENCE,
                evidence=["provisional-alias"],
                families=len({item.source_family for item in evidence}),
            ),
        )
    return AliasBelief(
        alias=alias,
        language=evidence[0].language,
        belief=make_belief(
            alias,
            confidence=min(0.85, max(item.confidence for item in evidence)),
            fact_class=FactClass.INFERRED,
            origin=FactOrigin.INFERENCE,
            evidence=["promoted-alias"],
            families=len({item.source_family for item in evidence}),
        ),
    )
