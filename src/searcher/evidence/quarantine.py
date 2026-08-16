"""Quarantine zone placement for untrusted bytes."""

from __future__ import annotations

from enum import StrEnum

from searcher.evidence.content_store import ContentStore


class QuarantineReason(StrEnum):
    SIZE_CAP = "size_cap"
    PATH_ESCAPE = "path_escape"
    POLICY = "policy"
    MALFORMED = "malformed"
    UNTRUSTED_SOURCE = "untrusted_source"
    MANUAL = "manual"


def quarantine(
    store: ContentStore,
    data: bytes,
    *,
    search_id: str,
    reason: QuarantineReason,
) -> str:
    """Write bytes into the quarantine zone and record ownership."""
    return store.put_bytes(
        data,
        zone="quarantine",
        campaign_id=search_id,
        private=True,
        extra_meta={"quarantine_reason": reason.value},
    )
