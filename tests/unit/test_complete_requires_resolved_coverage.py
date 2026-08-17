"""COMPLETE is a coverage claim, so an unresolved source must forbid it.

Fault injection found COMPLETE returned after a 21.5s source timeout, a 20.4s
hang, a 9.8s redirect loop, and an HTTP 200 whose body could not be parsed. The
existing rule only refused COMPLETE when nothing at all was fetched, so a
campaign that fetched pages and then lost a source still told the user its
search was complete.

PARTIAL is the honest word for searched-but-incomplete, and the coverage map
already records which source it was.
"""

from __future__ import annotations

import pytest

from searcher.campaigns.publication import published_terminal_status
from searcher.contracts.enums import CampaignState, SourceOutcome


def _status(outcomes: dict[str, str] | None) -> str:
    return published_terminal_status(
        proposed=CampaignState.COMPLETE.value,
        pages_fetched=17,
        candidate_count=24,
        source_outcomes=outcomes,
    )


def test_all_sources_answered_still_completes() -> None:
    assert _status(
        {
            "kind": SourceOutcome.SEARCHED_MATCHES_FOUND.value,
            "rebag": SourceOutcome.SEARCHED_NO_MATCH.value,
        }
    ) == CampaignState.COMPLETE.value


@pytest.mark.parametrize(
    "outcome",
    [
        SourceOutcome.NETWORK_FAILED.value,
        SourceOutcome.PARSER_FAILED.value,
        SourceOutcome.RATE_LIMITED.value,
        SourceOutcome.SOURCE_UNAVAILABLE.value,
        SourceOutcome.UNMEASURABLE.value,
        SourceOutcome.NOT_ATTEMPTED.value,
    ],
)
def test_an_unresolved_source_forbids_complete(outcome: str) -> None:
    status = _status({"kind": SourceOutcome.SEARCHED_MATCHES_FOUND.value, "other": outcome})
    assert status == CampaignState.PARTIAL.value, (
        f"a campaign carrying {outcome} claimed COMPLETE"
    )


def test_a_policy_block_is_not_an_unresolved_source() -> None:
    """A source refused by policy or robots was resolved: we know the answer."""
    for resolved in (
        SourceOutcome.BLOCKED_BY_POLICY.value,
        SourceOutcome.BLOCKED_BY_ACCESS.value,
        SourceOutcome.AUTH_REQUIRED.value,
    ):
        assert _status({"a": SourceOutcome.SEARCHED_NO_MATCH.value, "b": resolved}) == (
            CampaignState.COMPLETE.value
        )


def test_callers_that_pass_nothing_keep_the_old_behaviour() -> None:
    assert _status(None) == CampaignState.COMPLETE.value
