"""Legal transitions plus the §10.2 invariants as raising guards."""

from __future__ import annotations

from searcher.campaigns.models import TransitionContext
from searcher.campaigns.states import is_terminal
from searcher.contracts.enums import CampaignState
from searcher.core.errors import ErrorClass, IllegalTransition, InvariantViolation

# Linear happy-path plus the documented loops and terminal exits.
_FORWARD: dict[CampaignState, frozenset[CampaignState]] = {
    CampaignState.CREATED: frozenset(
        {CampaignState.VALIDATING_INPUT, CampaignState.CANCELLED, CampaignState.FAILED}
    ),
    CampaignState.VALIDATING_INPUT: frozenset(
        {
            CampaignState.INGESTING_REFERENCES,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.INGESTING_REFERENCES: frozenset(
        {
            CampaignState.CALIBRATING_REFERENCES,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.CALIBRATING_REFERENCES: frozenset(
        {
            CampaignState.DECOMPOSING_REFERENCES,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.DECOMPOSING_REFERENCES: frozenset(
        {
            CampaignState.FORMING_HYPOTHESES,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.FORMING_HYPOTHESES: frozenset(
        {
            CampaignState.PLANNING_QUERIES,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.PLANNING_QUERIES: frozenset(
        {
            CampaignState.PLANNING_SOURCES,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.PLANNING_SOURCES: frozenset(
        {
            CampaignState.DISCOVERING,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.DISCOVERING: frozenset(
        {
            CampaignState.ACQUIRING,
            CampaignState.REPLANNING,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
            CampaignState.PARTIAL,
        }
    ),
    CampaignState.ACQUIRING: frozenset(
        {
            CampaignState.NORMALIZING,
            CampaignState.DISCOVERING,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.NORMALIZING: frozenset(
        {
            CampaignState.DEDUPLICATING,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.DEDUPLICATING: frozenset(
        {
            CampaignState.BROAD_RETRIEVAL,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.BROAD_RETRIEVAL: frozenset(
        {
            CampaignState.FINE_MATCHING,
            CampaignState.GAP_ANALYSIS,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.FINE_MATCHING: frozenset(
        {
            CampaignState.AUTHENTICITY_REVIEW,
            CampaignState.GAP_ANALYSIS,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.AUTHENTICITY_REVIEW: frozenset(
        {
            CampaignState.LIVE_CHECKING,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.LIVE_CHECKING: frozenset(
        {
            CampaignState.RANKING,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.RANKING: frozenset(
        {
            CampaignState.PUBLISHING,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.PUBLISHING: frozenset(
        {
            CampaignState.GAP_ANALYSIS,
            CampaignState.COMPLETE,
            CampaignState.PARTIAL,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.GAP_ANALYSIS: frozenset(
        {
            CampaignState.REPLANNING,
            CampaignState.COMPLETE,
            CampaignState.PARTIAL,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.REPLANNING: frozenset(
        {
            CampaignState.PLANNING_QUERIES,
            CampaignState.PLANNING_SOURCES,
            CampaignState.DISCOVERING,
            CampaignState.COMPLETE,
            CampaignState.PARTIAL,
            CampaignState.BLOCKED,
            CampaignState.CANCELLED,
            CampaignState.FAILED,
        }
    ),
    CampaignState.COMPLETE: frozenset(),
    CampaignState.PARTIAL: frozenset(),
    CampaignState.BLOCKED: frozenset(),
    CampaignState.FAILED: frozenset(),
    CampaignState.CANCELLED: frozenset(),
}

_INTERNAL_FAILURES = frozenset(
    {
        ErrorClass.INTERNAL_INVARIANT,
        ErrorClass.DATABASE,
        ErrorClass.STORAGE,
        ErrorClass.MODEL,
        ErrorClass.BROWSER,
    }
)


def legal_targets(source: CampaignState) -> frozenset[CampaignState]:
    return _FORWARD[source]


def assert_legal(
    source: CampaignState, target: CampaignState, *, search_id: str | None = None
) -> None:
    if is_terminal(source):
        raise IllegalTransition(
            f"cannot leave terminal state {source}",
            source=source.value,
            target=target.value,
            search_id=search_id,
        )
    if target not in _FORWARD[source]:
        raise IllegalTransition(
            f"illegal transition {source} -> {target}",
            source=source.value,
            target=target.value,
            search_id=search_id,
        )


def assert_invariants(
    source: CampaignState,
    target: CampaignState,
    context: TransitionContext,
    *,
    search_id: str | None = None,
) -> None:
    """§10.2 guards. Each raises if the invariant would be broken."""
    if target is CampaignState.DISCOVERING and not (
        context.has_query or context.has_visual_representation
    ):
        raise InvariantViolation(
            "cannot enter DISCOVERING without a query or visual search representation",
            search_id=search_id,
        )
    if target is CampaignState.FINE_MATCHING and context.normalized_candidate_count < 1:
        raise InvariantViolation(
            "cannot enter FINE_MATCHING without normalized candidates",
            search_id=search_id,
        )
    if target is CampaignState.AUTHENTICITY_REVIEW and (
        context.seller_text_only or not context.has_visual_or_normalized_evidence
    ):
        raise InvariantViolation(
            "a candidate cannot enter AUTHENTICITY_REVIEW from seller text alone",
            search_id=search_id,
        )
    if target is CampaignState.COMPLETE and not (
        context.exhaustion_receipt or context.saturation_receipt
    ):
        raise InvariantViolation(
            "COMPLETE requires a search-exhaustion or success-saturation receipt",
            search_id=search_id,
        )
    if target is CampaignState.FAILED:
        reason = (context.reason or "").lower()
        if context.error_class not in _INTERNAL_FAILURES:
            raise InvariantViolation(
                "FAILED requires an internal defect, not merely zero matches",
                search_id=search_id,
            )
        if "no match" in reason or "zero match" in reason:
            raise InvariantViolation(
                "FAILED requires an internal defect, not merely zero matches",
                search_id=search_id,
            )
    del source
