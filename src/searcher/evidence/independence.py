"""§3.3 / §17.5: cluster evidence into families; count independent families."""

from __future__ import annotations

from collections.abc import Sequence

from searcher.evidence.records import EvidenceRecord


def family_key(record: EvidenceRecord) -> str:
    """One photograph rehosted ten times shares one family key."""
    return record.family_id or record.content_digest


def independent_family_count(records: Sequence[EvidenceRecord]) -> int:
    """GUARD: duplicate evidence never increases the independent-evidence count.

    Ten pages sharing one photograph count once. Implementation is the size of
    the family-key set, not the record list. Counting `len(records)` instead
    is the mutation that must fail the property test.
    """
    families: set[str] = set()
    for record in records:
        families.add(family_key(record))
    return len(families)
