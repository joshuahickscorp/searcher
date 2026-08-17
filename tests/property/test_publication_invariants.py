"""Executable publication invariants. Generated inputs, not remembered examples.

Each test below fails if the guard it names is removed from publication.py:
a replica with a Real decision would publish as Real, a card with no URL or
no reason codes would publish, and COMPLETE would be returned for a campaign
that fetched nothing.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from searcher.authenticity.established import published_compare_parts
from searcher.authenticity.profiles import profile_for
from searcher.campaigns.publication import (
    has_usable_listing_link,
    published_public_bucket,
    published_terminal_status,
)
from searcher.contracts.enums import (
    Availability,
    BucketPublic,
    CampaignState,
    FactClass,
    FactOrigin,
)
from searcher.contracts.models import ListingCandidate
from searcher.contracts.primitives import classified
from searcher.core.ids import new_id
from searcher.core.time import parse_utc

_TS = parse_utc("2007-06-15T12:00:00+00:00")

_REPLICA_STEMS = ("replica", "counterfeit", "superfake", "repfam")
_HOMOGLYPHS = str.maketrans({"a": "а", "e": "е", "o": "о", "c": "с", "p": "р"})
_SAFE_LEET = str.maketrans({"e": "3", "o": "0", "a": "4", "s": "5"})
# The digit 1 stands for either l or i, so "r3pl1ca" and "rep1ica" are both
# readings of the same word. _SAFE_LEET leaves 1 out, which is why this
# generator could never produce the one obfuscation that actually got through:
# r3pl1ca published as Possibly Real. Detection now reads the ambiguous digit
# both ways, and the generator has to be able to write it or the property is
# only tested against the cases that already worked.
_AMBIGUOUS_LEET = str.maketrans({"e": "3", "o": "0", "a": "4", "s": "5", "i": "1", "l": "1"})
_OBFUSCATIONS = ("homoglyph", "zwsp", "digit", "spacing", "ambiguous_digit")


class _Decision:
    def __init__(
        self,
        public: BucketPublic,
        *,
        reason_codes: list[str] | None = None,
        hard_vetoes: list[str] | None = None,
    ) -> None:
        self.decision = type("D", (), {"public": public})()
        self.hard_vetoes = list(hard_vetoes or [])
        self.reason_codes = list(reason_codes or [])


def _candidate(*, title: str, url: str = "https://shop.example/item/1") -> ListingCandidate:
    return ListingCandidate(
        candidate_id=new_id(),
        canonical_url=url,
        source_adapter="ebay",
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        description=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )


def _obfuscate(stem: str, kind: str) -> str:
    text = stem
    if kind == "homoglyph":
        text = text.translate(_HOMOGLYPHS)
    elif kind == "digit":
        text = text.translate(_SAFE_LEET)
    elif kind == "ambiguous_digit":
        text = text.translate(_AMBIGUOUS_LEET)
    elif kind == "zwsp":
        text = "\u200b".join(text)
    elif kind == "spacing":
        text = " ".join(text)
    return text


@st.composite
def adversarial_replica_text(draw: st.DrawFn) -> str:
    stem = draw(st.sampled_from(_REPLICA_STEMS))
    kind = draw(st.sampled_from(_OBFUSCATIONS))
    extra = draw(
        st.lists(
            st.sampled_from(_OBFUSCATIONS),
            max_size=2,
            unique=True,
        )
    )
    text = stem
    for step in (kind, *extra):
        if step == "homoglyph":
            text = text.translate(_HOMOGLYPHS)
        elif step == "digit":
            text = "".join(ch if ch in {"\u200b", " "} else ch.translate(_SAFE_LEET) for ch in text)
        elif step == "ambiguous_digit":
            text = "".join(
                ch if ch in {"\u200b", " "} else ch.translate(_AMBIGUOUS_LEET) for ch in text
            )
        elif step == "zwsp" and "\u200b" not in text and " " not in text:
            text = "\u200b".join(text)
        elif step == "spacing" and " " not in text:
            text = " ".join(ch for ch in text if ch != "\u200b")
    prefix = draw(st.sampled_from(["", "Dior Homme GAT ", "listing title: "]))
    suffix = draw(st.sampled_from(["", " quality", " pair"]))
    return f"{prefix}{text}{suffix}"


@settings(max_examples=220)
@given(adversarial_replica_text())
def test_generated_replica_text_never_reaches_real(text: str) -> None:
    candidate = _candidate(title=text)
    decision = _Decision(BucketPublic.REAL, reason_codes=["real-gate"])
    bucket = published_public_bucket(decision, candidate)
    assert bucket != BucketPublic.REAL.value
    assert bucket == BucketPublic.REPLICA.value


@st.composite
def unusable_urls(draw: st.DrawFn) -> str:
    return draw(
        st.one_of(
            st.just(""),
            st.just("about:blank"),
            st.from_regex(r"javascript:[a-z0-9()]{0,24}", fullmatch=True),
            st.from_regex(r"data:text/[a-z]{1,8},[a-z0-9]{0,16}", fullmatch=True),
            st.from_regex(r"file:///[a-z0-9/._-]{1,24}", fullmatch=True),
            st.from_regex(r"/[a-z0-9/_-]{1,24}", fullmatch=True),
            st.from_regex(r"ftp://[a-z0-9.]{1,24}/[a-z0-9]{1,12}", fullmatch=True),
        )
    )


@settings(max_examples=80)
@given(unusable_urls())
def test_generated_unusable_url_is_never_published(url: str) -> None:
    candidate = _candidate(title="plain long sleeve cutsew", url=url)
    assert has_usable_listing_link(candidate) is False
    for public in (BucketPublic.REAL, BucketPublic.POSSIBLY_REAL):
        decision = _Decision(public, reason_codes=["real-gate"])
        assert published_public_bucket(decision, candidate) == BucketPublic.HIDDEN.value


@settings(max_examples=80)
@given(st.sampled_from([BucketPublic.REAL, BucketPublic.POSSIBLY_REAL]))
def test_a_result_without_reason_codes_is_never_published(public: BucketPublic) -> None:
    candidate = _candidate(title="plain long sleeve cutsew")
    decision = _Decision(public, reason_codes=[], hard_vetoes=[])
    assert published_public_bucket(decision, candidate) == BucketPublic.HIDDEN.value


@settings(max_examples=80)
@given(
    st.integers(min_value=0, max_value=12),
    st.integers(min_value=0, max_value=12),
    st.booleans(),
)
def test_complete_requires_a_fetch(
    pages_fetched: int, candidate_count: int, saturation: bool
) -> None:
    status = published_terminal_status(
        proposed=CampaignState.COMPLETE.value,
        pages_fetched=pages_fetched,
        candidate_count=candidate_count,
        saturation=saturation,
    )
    if saturation:
        assert status == CampaignState.COMPLETE.value
        return
    if pages_fetched <= 0 and candidate_count <= 0:
        assert status != CampaignState.COMPLETE.value
        assert status == CampaignState.BLOCKED.value
        return
    assert status == CampaignState.COMPLETE.value


@settings(max_examples=80)
@given(
    st.lists(
        st.sampled_from(
            [
                "eyelets",
                "outsole",
                "heel",
                "tongue",
                "midsole",
                "construction-heel",
                "collar",
                "label",
                "front",
            ]
        ),
        max_size=8,
    )
)
def test_generated_shoe_parts_never_publish_on_a_garment(names: list[str]) -> None:
    rows = published_compare_parts(names, profile_for("garment"))
    blob = json.dumps(rows).lower()
    assert "eyelet" not in blob
    assert "outsole" not in blob
    assert "heel" not in blob
    assert "tongue" not in blob
    assert "midsole" not in blob


@pytest.mark.parametrize("kind", list(_OBFUSCATIONS))
def test_each_obfuscation_class_is_caught(kind: str) -> None:
    text = f"Dior Homme GAT {_obfuscate('replica', kind)}"
    decision = _Decision(BucketPublic.REAL, reason_codes=["real-gate"])
    assert published_public_bucket(decision, _candidate(title=text)) == (
        BucketPublic.REPLICA.value
    )
