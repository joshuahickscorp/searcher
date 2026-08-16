"""Source and seller signals. Supportive, never decisive, never defamatory."""

from __future__ import annotations

from searcher.contracts.models import ListingCandidate
from searcher.contracts.primitives import ScoreWithEvidence
from searcher.matching.scores import scored
from searcher.retrieval.text import self_declared_replica


def assess_source(
    candidate: ListingCandidate,
    *,
    malicious_url: bool,
) -> tuple[ScoreWithEvidence, list[str], list[str]]:
    hard: list[str] = []
    text = " ".join(
        str(part.value) for part in (candidate.title, candidate.description) if part and part.value
    )
    if self_declared_replica(text):
        hard.append("self-declared-replica")
    if malicious_url:
        hard.append("malicious-url")
    meta = candidate.seller_metadata
    age = meta.get("account_age_days") if isinstance(meta, dict) else None
    payment = str(meta.get("payment") if isinstance(meta, dict) else "")
    mean = 0.55
    if isinstance(age, (int, float)) and age < 7:
        mean -= 0.08
    if payment.lower() in {"off-platform", "wire", "crypto-only"}:
        mean -= 0.08
    if hard:
        mean = 0.12
    # Platform authentication badges are recorded, never decisive.
    badge = meta.get("authenticated") if isinstance(meta, dict) else None
    support = ["ev:source:metadata"]
    if badge:
        support.append("ev:source:platform-badge-reported")
    return scored(max(0.08, mean), spread=0.14, support=support, contradictions=hard), hard, []
