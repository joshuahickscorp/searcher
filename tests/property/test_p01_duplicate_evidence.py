"""Property 1: duplicate evidence never increases the independent-evidence count."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import EvidencePolarity, FactClass
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.evidence.independence import independent_family_count
from searcher.evidence.lineage import raw_lineage
from searcher.evidence.records import EvidenceRecord

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def _record(family: str, digest: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=new_id(),
        search_id="s",
        content_digest=digest,
        family_id=family,
        polarity=EvidencePolarity.SUPPORTING,
        fact_class=FactClass.REPORTED_BY_SOURCE,
        accepted=True,
        lineage=raw_lineage(input_digests=[digest], process="test"),
        created_at=_TS,
    )


@given(st.lists(st.sampled_from(["fam-a", "fam-b", "fam-c"]), min_size=1, max_size=20))
def test_duplicate_evidence_never_increases_independent_count(families: list[str]) -> None:
    records = [_record(family, f"d{i:02d}{family}") for i, family in enumerate(families)]
    unique = set(families)
    assert independent_family_count(records) == len(unique)
    extras = [_record(families[0], "dup-" + families[0]) for _ in range(5)]
    assert independent_family_count(records + extras) == independent_family_count(records)
