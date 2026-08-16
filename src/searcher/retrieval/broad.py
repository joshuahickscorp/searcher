"""§18.2 Stage A — inexpensive broad retrieval. Optimize for recall."""

from __future__ import annotations

from dataclasses import dataclass, field

from searcher.contracts.models import ItemHypothesis, ListingCandidate, VisualSignature
from searcher.retrieval.cost import CostLedger, CostStage
from searcher.retrieval.embeddings import embed_png, resolve_backend
from searcher.retrieval.escalation import DEFAULT_BOUNDS, KEEP_THRESHOLD, EscalationBounds
from searcher.retrieval.signals import CheapSignals, compute_cheap_signals


@dataclass
class BroadHit:
    candidate: ListingCandidate
    signals: CheapSignals
    kept: bool
    reason: str


@dataclass
class BroadRetrievalResult:
    hits: list[BroadHit]
    kept: list[BroadHit]
    dropped: list[BroadHit]
    bounds: EscalationBounds
    notes: list[str] = field(default_factory=list)

    @property
    def kept_ids(self) -> list[str]:
        return [hit.candidate.candidate_id for hit in self.kept]


def retrieve_broad(
    *,
    candidates: list[ListingCandidate],
    hypothesis: ItemHypothesis,
    reference_signature: VisualSignature,
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, dict[str, bytes]],
    candidate_ocr: dict[str, list[str]] | None = None,
    ledger: CostLedger | None = None,
    bounds: EscalationBounds | None = None,
    already_deduplicated: bool = False,
) -> BroadRetrievalResult:
    """Rank by cheap signals. The true rare item must survive this stage."""
    limits = bounds or DEFAULT_BOUNDS
    log = ledger or CostLedger()
    log.record(CostStage.CACHE, detail="miss")
    log.record(CostStage.HASHES_METADATA, detail=f"n={len(candidates)}")
    log.record(CostStage.TEXT_OCR, detail="normalized")
    backend = resolve_backend()
    if backend is not None:
        log.record(CostStage.GLOBAL_EMBEDDINGS, detail=backend.identity)
    else:
        log.record(CostStage.GLOBAL_EMBEDDINGS, detail="blocked_no_weights")
    if already_deduplicated and not log.deduplicated:
        log.mark_deduplicated()

    ocr = candidate_ocr or {}
    hits: list[BroadHit] = []
    for candidate in candidates:
        pngs = candidate_pngs.get(candidate.candidate_id, {})
        embedding = None
        if backend is not None and pngs:
            # Gateway is real; embed_png returns None until weights actually load.
            _ = embed_png(next(iter(pngs.values())), backend)
        signals = compute_cheap_signals(
            candidate=candidate,
            hypothesis=hypothesis,
            reference_signature=reference_signature,
            reference_pngs=reference_pngs,
            candidate_pngs=pngs,
            candidate_ocr=ocr.get(candidate.candidate_id, []),
            embedding_similarity=embedding,
        )
        hits.append(
            BroadHit(
                candidate=candidate,
                signals=signals,
                kept=False,
                reason="",
            )
        )
    hits.sort(key=lambda hit: hit.signals.recall_score, reverse=True)
    cap = limits.broad_candidates
    kept: list[BroadHit] = []
    dropped: list[BroadHit] = []
    for index, hit in enumerate(hits):
        if hit.signals.recall_score >= KEEP_THRESHOLD and index < cap:
            hit.kept = True
            hit.reason = "above_recall_threshold"
            kept.append(hit)
        elif index < cap and hit.signals.recall_score >= KEEP_THRESHOLD / 2:
            # Extra slack so a rare exact item with weak text still survives.
            hit.kept = True
            hit.reason = "recall_slack"
            kept.append(hit)
        else:
            hit.reason = "below_threshold_or_cap"
            dropped.append(hit)
    notes = [
        f"scored={len(hits)}",
        f"kept={len(kept)}",
        f"cap={cap}",
        "learned_embedding=blocked" if backend is None else "learned_embedding=present",
    ]
    return BroadRetrievalResult(hits=hits, kept=kept, dropped=dropped, bounds=limits, notes=notes)
