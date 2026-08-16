"""State machine illegal-transition refusal and §10.2 guards."""

from __future__ import annotations

import pytest

from searcher.campaigns.models import TransitionContext
from searcher.campaigns.transitions import assert_invariants, assert_legal
from searcher.contracts.enums import CampaignState
from searcher.core.errors import ErrorClass, IllegalTransition, InvariantViolation


def test_created_to_validating_is_legal() -> None:
    assert_legal(CampaignState.CREATED, CampaignState.VALIDATING_INPUT)


def test_illegal_skip_raises() -> None:
    with pytest.raises(IllegalTransition):
        assert_legal(CampaignState.CREATED, CampaignState.DISCOVERING)


def test_cannot_leave_terminal() -> None:
    with pytest.raises(IllegalTransition):
        assert_legal(CampaignState.COMPLETE, CampaignState.CREATED)


def test_discovering_requires_query_or_visual() -> None:
    with pytest.raises(InvariantViolation, match="DISCOVERING"):
        assert_invariants(
            CampaignState.PLANNING_SOURCES,
            CampaignState.DISCOVERING,
            TransitionContext(),
        )
    assert_invariants(
        CampaignState.PLANNING_SOURCES,
        CampaignState.DISCOVERING,
        TransitionContext(has_query=True),
    )


def test_fine_matching_requires_normalized_candidates() -> None:
    with pytest.raises(InvariantViolation, match="FINE_MATCHING"):
        assert_invariants(
            CampaignState.BROAD_RETRIEVAL,
            CampaignState.FINE_MATCHING,
            TransitionContext(normalized_candidate_count=0),
        )


def test_authenticity_rejects_seller_text_only() -> None:
    with pytest.raises(InvariantViolation, match="seller text"):
        assert_invariants(
            CampaignState.FINE_MATCHING,
            CampaignState.AUTHENTICITY_REVIEW,
            TransitionContext(seller_text_only=True, has_visual_or_normalized_evidence=False),
        )


def test_complete_requires_receipt() -> None:
    with pytest.raises(InvariantViolation, match="exhaustion"):
        assert_invariants(
            CampaignState.GAP_ANALYSIS,
            CampaignState.COMPLETE,
            TransitionContext(),
        )
    assert_invariants(
        CampaignState.GAP_ANALYSIS,
        CampaignState.COMPLETE,
        TransitionContext(exhaustion_receipt="r1"),
    )


def test_failed_requires_internal_defect() -> None:
    with pytest.raises(InvariantViolation, match="internal defect"):
        assert_invariants(
            CampaignState.DISCOVERING,
            CampaignState.FAILED,
            TransitionContext(reason="no matches"),
        )
    with pytest.raises(InvariantViolation, match="internal defect"):
        assert_invariants(
            CampaignState.DISCOVERING,
            CampaignState.FAILED,
            TransitionContext(error_class=ErrorClass.INTERNAL_INVARIANT, reason="zero matches"),
        )
    assert_invariants(
        CampaignState.DISCOVERING,
        CampaignState.FAILED,
        TransitionContext(error_class=ErrorClass.INTERNAL_INVARIANT, reason="sqlite corrupted"),
    )
