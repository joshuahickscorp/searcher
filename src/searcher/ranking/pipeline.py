"""End-to-end judgment: retrieval → match → authenticity → route → rank."""

from __future__ import annotations

from dataclasses import dataclass, field

from searcher.authenticity.completeness import completeness
from searcher.authenticity.engine import assess_authenticity
from searcher.authenticity.profiles import profile_for
from searcher.contracts.enums import BucketPublic
from searcher.contracts.models import (
    AuthenticityEvidence,
    BucketDecision,
    ItemHypothesis,
    ListingCandidate,
    ListingUtility,
    MatchEvidence,
    SearchConstraints,
)
from searcher.matching.adjudicator import local_adjudicate, should_adjudicate
from searcher.matching.compare import ComparisonArtifact, render_comparison
from searcher.matching.ontology import ontology_for
from searcher.matching.pipeline import enrich_candidate, match_candidate, prepare_reference
from searcher.ranking.buckets import route_candidate
from searcher.ranking.diversity import diversify
from searcher.ranking.order import RankedResult, rank_tab
from searcher.ranking.policy_versions import BucketPolicy, load_policy
from searcher.ranking.questions import answer_questions
from searcher.ranking.utility import listing_utility
from searcher.receipts.types import BucketDecisionReceipt, CostReceipt
from searcher.retrieval.cost import CostLedger
from searcher.retrieval.escalation import DEFAULT_BOUNDS, EscalationBounds
from searcher.retrieval.pipeline import run_broad_retrieval


@dataclass
class JudgmentBundle:
    candidate: ListingCandidate
    match: MatchEvidence
    authenticity: AuthenticityEvidence
    utility: ListingUtility
    decision: BucketDecision
    answers: dict[str, object]
    comparison: ComparisonArtifact | None = None


@dataclass
class JudgmentReport:
    retrieval_ids: list[str]
    bundles: list[JudgmentBundle]
    ranked_real: list[RankedResult]
    ranked_possible: list[RankedResult]
    ledger: CostLedger
    cost_receipt: CostReceipt
    policy_version: str
    notes: list[str] = field(default_factory=list)

    @property
    def decisions(self) -> list[BucketDecision]:
        return [bundle.decision for bundle in self.bundles]


def judge_candidates(
    *,
    search_id: str,
    hypothesis: ItemHypothesis,
    candidates: list[ListingCandidate],
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, dict[str, bytes]],
    constraints: SearchConstraints | None = None,
    already_deduplicated: bool = True,
    destination_verified: dict[str, bool] | None = None,
    stolen: set[str] | None = None,
    stock_mixed: set[str] | None = None,
    policy: BucketPolicy | None = None,
    bounds: EscalationBounds | None = None,
    render_artifacts: bool = True,
) -> JudgmentReport:
    ledger = CostLedger(search_id=search_id)
    limits = bounds or DEFAULT_BOUNDS
    bundle_policy = policy or load_policy("matching-1")
    retrieval = run_broad_retrieval(
        candidates=candidates,
        hypothesis=hypothesis,
        reference_signature=hypothesis.visual_signature,
        reference_pngs=reference_pngs,
        candidate_pngs=candidate_pngs,
        ledger=ledger,
        bounds=limits,
        already_deduplicated=True,
    )
    kept = retrieval.kept
    if not kept:
        kept = retrieval.hits[: limits.clip(len(retrieval.hits), stage="broad")]
    ref_desc = prepare_reference(reference_pngs, ledger=ledger)
    ontology = ontology_for(hypothesis.category)
    dest = destination_verified or {}
    stolen_ids = stolen or set()
    stock_ids = stock_mixed or set()
    part_cap = limits.part_matching
    deep_cap = limits.deep_authenticity
    delib_cap = limits.deliberative_review
    bundles: list[JudgmentBundle] = []
    utilities: dict[str, ListingUtility] = {}
    families: dict[str, str] = {}
    ref_png = next(iter(reference_pngs.values())) if reference_pngs else None
    for rank, hit in enumerate(kept[:part_cap]):
        candidate = hit.candidate
        pngs = candidate_pngs.get(candidate.candidate_id, {})
        enriched = enrich_candidate(candidate, pngs, ontology=ontology, ledger=ledger)
        match = match_candidate(
            hypothesis=hypothesis,
            candidate=enriched,
            reference_pngs=reference_pngs,
            reference_descriptors=ref_desc,
            constraints=constraints,
            ledger=ledger,
        )
        auth = assess_authenticity(
            hypothesis=hypothesis,
            candidate=enriched,
            reference_descriptors=ref_desc,
            constraints=constraints,
            stolen_photo=candidate.candidate_id in stolen_ids,
            stock_mixed=candidate.candidate_id in stock_ids,
            ledger=ledger,
            deep=rank < deep_cap,
        )
        utility = listing_utility(
            candidate,
            constraints=constraints,
            destination_verified=dest.get(candidate.candidate_id, False),
        )
        utilities[candidate.candidate_id] = utility
        complete, _ = completeness(
            profile=profile_for(hypothesis.category),
            present_views={view.view.value for view in enriched.views},
        )
        decision = route_candidate(
            candidate=candidate,
            match=match,
            authenticity=auth,
            utility=utility,
            completeness_value=complete,
            constraints=constraints,
            destination_verified=dest.get(candidate.candidate_id, False),
            stolen_photo=candidate.candidate_id in stolen_ids,
            policy=bundle_policy,
        )
        near = abs(match.item_match_distribution.lower_bound - 0.90) < 0.08
        if should_adjudicate(
            rank=rank,
            deliberative_cap=delib_cap,
            hard_item=list(match.hard_contradictions),
            hard_auth=list(auth.hard_contradictions),
            near_boundary=near,
            needs_explanation=True,
            conflict=bool(match.hard_contradictions) and bool(match.hard_support),
        ):
            text = (
                str(candidate.description.value)
                if candidate.description and candidate.description.value
                else None
            )
            advice = local_adjudicate(
                listing_text=text,
                support=list(match.explanation.support),
                contradictions=list(match.hard_contradictions),
                missing=list(match.missing_views),
                ledger=ledger,
            )
            decision = decision.model_copy(
                update={"reason_codes": list(decision.reason_codes) + advice.notes[:2]}
            )
        comparison = None
        if render_artifacts and ref_png and pngs:
            comparison = render_comparison(
                reference_png=ref_png,
                candidate_png=next(iter(pngs.values())),
                agreed=list(match.explanation.support)[:6],
                disagreed=list(match.hard_contradictions)[:6],
                missing=list(match.missing_views)[:6],
                title=f"{candidate.candidate_id} {decision.decision.public.value}",
            )
        answers = answer_questions(
            candidate=candidate,
            match=match,
            authenticity=auth,
            utility=utility,
            decision=decision,
        )
        if candidate.cluster_id:
            family = candidate.cluster_id
        elif enriched.image_family_ids:
            family = enriched.image_family_ids[0]
        else:
            family = candidate.candidate_id
        families[candidate.candidate_id] = family
        bundles.append(
            JudgmentBundle(
                candidate=candidate,
                match=match,
                authenticity=auth,
                utility=utility,
                decision=decision,
                answers=answers,
                comparison=comparison,
            )
        )
    real = rank_tab(
        public=BucketPublic.REAL,
        decisions=[b.decision for b in bundles],
        utilities=utilities,
        weights=bundle_policy.ranking,
    )
    possible = rank_tab(
        public=BucketPublic.POSSIBLY_REAL,
        decisions=[b.decision for b in bundles],
        utilities=utilities,
        weights=bundle_policy.ranking,
    )
    real = diversify(real, family_of=families, public=BucketPublic.REAL)
    possible = diversify(possible, family_of=families, public=BucketPublic.POSSIBLY_REAL)
    cost = CostReceipt(
        search_id=search_id,
        stages=ledger.stage_names(),
        cache_hits=ledger.cache_hits,
        model_calls=ledger.model_calls,
        bytes_touched=ledger.bytes_touched,
        dedup_savings=ledger.dedup_savings,
        cheap_first=ledger.cheap_first_respected(),
    ).seal()
    return JudgmentReport(
        retrieval_ids=retrieval.kept_ids,
        bundles=bundles,
        ranked_real=real,
        ranked_possible=possible,
        ledger=ledger,
        cost_receipt=cost,
        policy_version=bundle_policy.version,
        notes=list(retrieval.notes),
    )


def seal_decision_receipt(search_id: str, decision: BucketDecision) -> BucketDecisionReceipt:
    return BucketDecisionReceipt(
        search_id=search_id,
        candidate_id=decision.candidate_id,
        internal=decision.decision.internal.value,
        public=decision.decision.public.value,
        policy_version=decision.policy_version,
    ).seal()
