"""§10.1 campaign states and terminal classification."""

from __future__ import annotations

from searcher.contracts.enums import TERMINAL_STATES, CampaignState, TerminalVerdict

ACTIVE_STATES = frozenset(s for s in CampaignState if s not in TERMINAL_STATES)

CHECKPOINT_AFTER: dict[CampaignState, str] = {
    CampaignState.VALIDATING_INPUT: "input_validation",
    CampaignState.INGESTING_REFERENCES: "reference_ingestion",
    CampaignState.DECOMPOSING_REFERENCES: "reference_analysis",
    CampaignState.FORMING_HYPOTHESES: "initial_hypothesis_portfolio",
    CampaignState.PLANNING_QUERIES: "initial_query_portfolio",
    CampaignState.DISCOVERING: "source_batch",
    CampaignState.NORMALIZING: "normalized_candidate_batch",
    CampaignState.BROAD_RETRIEVAL: "broad_retrieval",
    CampaignState.FINE_MATCHING: "fine_match_promotion",
    CampaignState.AUTHENTICITY_REVIEW: "authenticity_decision",
    CampaignState.PUBLISHING: "result_publication",
    CampaignState.REPLANNING: "replan",
    CampaignState.COMPLETE: "terminal",
    CampaignState.PARTIAL: "terminal",
    CampaignState.BLOCKED: "terminal",
    CampaignState.FAILED: "terminal",
    CampaignState.CANCELLED: "terminal",
}


def is_terminal(state: CampaignState) -> bool:
    return state in TERMINAL_STATES


def terminal_verdict_for(state: CampaignState) -> TerminalVerdict | None:
    if state is CampaignState.COMPLETE:
        return TerminalVerdict.COMPLETE
    if state is CampaignState.PARTIAL:
        return TerminalVerdict.PARTIAL
    if state is CampaignState.BLOCKED:
        return TerminalVerdict.BLOCKED
    if state is CampaignState.FAILED:
        return TerminalVerdict.FAILED
    if state is CampaignState.CANCELLED:
        return TerminalVerdict.CANCELLED
    return None
