"""G072: the Replica scope returns findings, or the interface says why it cannot.

Every replica source is disabled for a stated reason - Taobao's robots
disallows its query-string item URLs, Weidian serves no robots file, Yupoo
returns 404 for both /robots.txt and its album paths - and admitting any of
them would mean ignoring a robots rule or working around an anti-automation
gate. The first clause of that obligation is genuinely blocked.

The second clause is not, and was unmet: the scope control was withdrawn from
the interface, so the page neither offered replica search nor explained its
absence. A reader saw no replica results and no reason for it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PAGE = Path("web/index.html")


def _page() -> str:
    if not PAGE.is_file():
        pytest.skip("web/index.html is not present")
    return PAGE.read_text(encoding="utf-8")


def test_the_page_explains_why_replica_sources_are_not_searched() -> None:
    text = _page()
    assert "Why replica sources are not searched" in text


def test_the_explanation_names_each_refused_source_and_its_reason() -> None:
    text = _page()
    for source in ("Taobao", "Weidian", "Yupoo"):
        assert source in text, f"{source} is refused but never named to the reader"
    assert "robots" in text.lower()


def test_the_page_says_absence_is_not_evidence_of_absence() -> None:
    """The dangerous reading is that no replica result means no replica exists."""
    text = _page()
    assert "never evidence" in text or "not evidence" in text


def test_the_page_still_states_a_replica_can_never_rank_real() -> None:
    text = _page()
    assert "never be ranked Real" in text


def test_the_page_never_claims_replica_sources_are_searched() -> None:
    """The page said both things at once.

    A public-claim audit found `web/index.html` still asserting "Replica
    sources are searched to find replicas" on the same page as the section
    explaining that they are not. Adding an explanation without removing the
    claim it contradicts leaves the reader with a flat falsehood above the
    correction.
    """
    text = _page()
    assert "sources are searched to find replicas" not in text
    assert "Replica sources are not searched" in text


def test_the_page_does_not_offer_false_real_zero_as_authenticity_evidence() -> None:
    """`false Real 0` measures identity under absent screening, not authenticity.

    The page quoted it inside its definition of Real, where a reader takes it as
    the rate at which Searcher wrongly calls a fake genuine. It is not that. The
    figure comes from a benchmark run in which photograph screening never ran,
    so the shapes it would need to catch - a listing reusing the brand's own
    images - are outside what it measures.
    """
    text = _page()
    assert "false Real 0" in text, "the figure may be published, but not unqualified"
    assert "not</strong> evidence about authenticity" in text or (
        "not evidence about authenticity" in text
    ), "the page must say what false Real 0 does not measure"
    assert "screening absent" in text or "never screened" in text
