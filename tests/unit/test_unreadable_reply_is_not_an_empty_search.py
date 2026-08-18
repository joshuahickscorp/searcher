"""A 200 we cannot read is a parse failure, not an empty result.

`PARSER_FAILED` was read in `sources/health.py` and `campaigns/publication.py`
and assigned nowhere. Adapters were made defensive so a hostile body returns no
listings instead of raising - right for crashing on binary and truncated
replies, and it traded a loud failure for a quiet one: an unparseable 200
reported SEARCHED_NO_MATCH, which tells a user the source was searched and had
nothing in it.

It also left the COMPLETE rule weaker than it reads. That rule forbids COMPLETE
when a planned source ended PARSER_FAILED, and the branch was dead while nothing
assigned it, so a campaign that could not read a reply could still call its
coverage complete.
"""

from __future__ import annotations

import pytest

from searcher.contracts.enums import SourceOutcome
from searcher.sources.statuses import classify_http


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"<html><body>listings</body></html>", id="html"),
        pytest.param(b"  <!DOCTYPE html><p>x", id="doctype-with-leading-space"),
        pytest.param(b'{"products": []}', id="json-object"),
        pytest.param(b"[]", id="json-array"),
        pytest.param(b"<?xml version='1.0'?><urlset/>", id="xml-sitemap"),
    ],
)
def test_a_readable_reply_is_not_a_parse_failure(body: bytes) -> None:
    assert classify_http(200, body=body) is not SourceOutcome.PARSER_FAILED


def test_an_empty_body_is_an_answer_not_a_failure() -> None:
    """Nothing to read is a real empty result; unreadable content is not."""
    assert classify_http(200, body=b"") is not SourceOutcome.PARSER_FAILED
    assert classify_http(200, body=b"   \n ") is not SourceOutcome.PARSER_FAILED


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"\x00\x01\xff\xfe binary", id="binary"),
        pytest.param(b"Service temporarily down", id="prose"),
        pytest.param(b"ERR_CONNECTION_RESET", id="error-string"),
    ],
)
def test_an_unreadable_reply_reports_a_parse_failure(body: bytes) -> None:
    assert classify_http(200, body=body) is SourceOutcome.PARSER_FAILED


def test_a_challenge_still_outranks_a_parse_failure() -> None:
    """Being blocked is the more specific and more actionable fact."""
    assert classify_http(200, body=b"anything", challenge=True) is SourceOutcome.BLOCKED_BY_ACCESS


def test_the_complete_rule_now_has_a_reachable_branch() -> None:
    from searcher.campaigns.publication import published_terminal_status
    from searcher.contracts.enums import CampaignState

    status = published_terminal_status(
        proposed=CampaignState.COMPLETE.value,
        pages_fetched=10,
        candidate_count=5,
        source_outcomes={"a": SourceOutcome.SEARCHED_NO_MATCH.value,
                         "b": SourceOutcome.PARSER_FAILED.value},
    )
    assert status == CampaignState.PARTIAL.value, (
        "a campaign that could not read a source's reply must not claim complete coverage"
    )
