"""§20 Real / Possibly Real routing. Versioned policy, replayable receipts."""

from __future__ import annotations

from searcher.contracts.enums import Availability, BucketPublic, HumanReview
from searcher.contracts.models import (
    AuthenticityEvidence,
    BucketDecision,
    BucketDecisionFields,
    ListingCandidate,
    ListingUtility,
    MatchEvidence,
    SearchConstraints,
)
from searcher.contracts.primitives import PublicExplanation
from searcher.contracts.routing import internal_bucket_from_public
from searcher.core.policy import GateView, evaluate_possibly_real_gate, evaluate_real_gate
from searcher.ranking.policy_versions import BucketPolicy, load_policy
from searcher.ranking.vetoes import collect_hard_vetoes


def route_candidate(
    *,
    candidate: ListingCandidate,
    match: MatchEvidence,
    authenticity: AuthenticityEvidence,
    utility: ListingUtility,
    completeness_value: float,
    constraints: SearchConstraints | None = None,
    destination_verified: bool = False,
    destination_attested: bool = False,
    stolen_photo: bool = False,
    duplicate_no_utility: bool = False,
    policy: BucketPolicy | None = None,
    live_checked: bool = True,
) -> BucketDecision:
    bundle = policy or load_policy("matching-1")
    item_lb = match.item_match_distribution.lower_bound
    auth_lb = authenticity.authenticity_distribution.lower_bound
    if bundle.require_calibrated_for_real and authenticity.authority_ceiling.startswith(
        "uncalibrated"
    ):
        # Uncalibrated authenticity cannot satisfy the Real gate.
        auth_for_real = min(auth_lb, bundle.real.authenticity_lower_bound - 0.01)
    else:
        auth_for_real = auth_lb
    vetoes = collect_hard_vetoes(
        candidate=candidate,
        item_hard=list(match.hard_contradictions),
        auth_hard=list(authenticity.hard_contradictions),
        item_lower=item_lb,
        destination_verified=destination_verified,
        destination_attested=destination_attested,
        stolen_photo=stolen_photo,
        duplicate_no_utility=duplicate_no_utility,
        dead_listing_is_hard_veto=bundle.dead_listing_is_hard_veto,
        plausible_floor=bundle.possibly.plausible_item_match_lower_bound,
        exact_colour_required=bool(constraints and constraints.colour),
    )
    view = GateView(
        item_match_lower_bound=item_lb,
        authenticity_lower_bound=auth_for_real,
        evidence_completeness=completeness_value,
        availability=candidate.availability.value,
        live_checked=live_checked and utility.live,
        destination_verified=destination_verified,
        hard_item_contradictions=list(match.hard_contradictions),
        hard_authenticity_contradictions=list(authenticity.hard_contradictions),
        hard_visual_vetoes=[v for v in vetoes if v in {"WRONG_PRODUCT", "HARD_COLOURWAY"}],
        scam_or_malicious=any(
            v in {"MALICIOUS_URL", "IMAGE_THEFT_OR_SCAM", "SELF_DECLARED_REPLICA"} for v in vetoes
        ),
        hard_vetoes=vetoes,
    )
    if vetoes:
        public = BucketPublic.HIDDEN
    elif evaluate_real_gate(view, bundle.real):
        public = BucketPublic.REAL
    elif evaluate_possibly_real_gate(view, bundle.possibly):
        public = BucketPublic.POSSIBLY_REAL
    else:
        public = BucketPublic.HIDDEN
    # Dead listing cannot be Real even if the policy forgot.
    if public is BucketPublic.REAL and candidate.availability is not Availability.LIVE:
        if bundle.dead_listing_is_hard_veto:
            public = BucketPublic.HIDDEN
        else:
            public = BucketPublic.POSSIBLY_REAL
    internal = internal_bucket_from_public(public, hard_vetoes=vetoes)
    reasons = list(vetoes)
    if public is BucketPublic.REAL:
        reasons.append("real-gate")
    elif public is BucketPublic.POSSIBLY_REAL:
        reasons.append("possibly-real-gate")
    else:
        reasons.append("hidden")
    explanation = PublicExplanation(
        support=list(match.explanation.support)[:6],
        contradictions=list(match.hard_contradictions) + list(authenticity.hard_contradictions),
        missing_evidence=list(authenticity.missing_evidence),
        live_status=candidate.availability,
        last_checked_at=candidate.last_checked_at,
        compared_images=list(match.explanation.compared_images),
        duplicate_image_families=list(match.explanation.duplicate_image_families),
        seller_reported_fields=list(match.explanation.seller_reported_fields),
    )
    return BucketDecision(
        candidate_id=candidate.candidate_id,
        decision=BucketDecisionFields(internal=internal, public=public),
        policy_version=bundle.version,
        item_match_lower_bound=item_lb,
        authenticity_lower_bound=auth_lb,
        evidence_completeness=completeness_value,
        hard_vetoes=vetoes,
        reason_codes=reasons,
        human_review=HumanReview.NOT_REQUIRED,
        explanation=explanation,
    )
