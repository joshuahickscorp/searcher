"""Duplicate images do not increase independent evidence."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from searcher.contracts.enums import EvidencePolarity, FactClass
from searcher.core.ids import new_id, sha256_hex
from searcher.core.time import parse_utc
from searcher.deduplication.images import content_fingerprint
from searcher.evidence.independence import independent_family_count
from searcher.evidence.lineage import raw_lineage
from searcher.evidence.records import EvidenceRecord

_TS = parse_utc("2007-06-15T12:00:00+00:00")


@given(st.binary(min_size=8, max_size=64), st.integers(min_value=1, max_value=8))
def test_same_bytes_same_family(data: bytes, copies: int) -> None:
    digest = sha256_hex(data)
    fingerprint = content_fingerprint(data)
    records = [
        EvidenceRecord(
            evidence_id=new_id(),
            search_id="s",
            content_digest=digest,
            family_id=fingerprint or digest,
            polarity=EvidencePolarity.SUPPORTING,
            fact_class=FactClass.REPORTED_BY_SOURCE,
            accepted=True,
            lineage=raw_lineage(input_digests=[digest], process="image"),
            created_at=_TS,
        )
        for _ in range(copies)
    ]
    assert independent_family_count(records) == 1
