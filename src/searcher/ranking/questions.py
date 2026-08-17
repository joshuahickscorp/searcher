"""§3.10: every public result answers ten questions from stored evidence."""

from __future__ import annotations

from searcher.authenticity.established import established_claims, unestablished_tokens
from searcher.authenticity.profiles import profile_for
from searcher.contracts.models import (
    AuthenticityEvidence,
    BucketDecision,
    ListingCandidate,
    ListingUtility,
    MatchEvidence,
)

QUESTIONS = (
    "why_same_item",
    "why_this_tab",
    "supporting_evidence",
    "conflicting_evidence",
    "missing_evidence",
    "listing_live",
    "last_checked",
    "images_compared",
    "duplicate_image_families",
    "seller_reported",
)


def answer_questions(
    *,
    candidate: ListingCandidate,
    match: MatchEvidence,
    authenticity: AuthenticityEvidence,
    utility: ListingUtility,
    decision: BucketDecision,
) -> dict[str, object]:
    explanation = decision.explanation
    profile = profile_for(authenticity.reference_class)
    missing = established_claims(list(explanation.missing_evidence), profile)
    for token in unestablished_tokens(profile):
        if token not in missing:
            missing.append(token)
    return {
        "why_same_item": established_claims(list(match.explanation.support), profile),
        "why_this_tab": list(decision.reason_codes),
        "supporting_evidence": established_claims(
            list(explanation.support) + list(match.hard_support),
            profile,
        ),
        "conflicting_evidence": established_claims(list(explanation.contradictions), profile),
        "missing_evidence": missing,
        "listing_live": (
            explanation.live_status.value
            if explanation.live_status is not None
            else candidate.availability.value
        ),
        "last_checked": (
            explanation.last_checked_at.isoformat()
            if explanation.last_checked_at
            else (candidate.last_checked_at.isoformat() if candidate.last_checked_at else None)
        ),
        "images_compared": list(explanation.compared_images),
        "duplicate_image_families": list(explanation.duplicate_image_families),
        "seller_reported": list(explanation.seller_reported_fields),
        "item_match_kind": match.judgment.kind.value if match.judgment else "ITEM_MATCH",
        "authenticity_kind": authenticity.judgment.kind.value,
        "utility_kind": utility.judgment.kind.value,
        "authenticity_label_calibrated": not authenticity.authority_ceiling.startswith(
            "uncalibrated"
        ),
    }
