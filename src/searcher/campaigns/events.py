"""Append-only campaign event log (§30.2) with §25.4 public names."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from searcher import SCHEMA_VERSION
from searcher.contracts.enums import PublicEventName
from searcher.contracts.primitives import SearcherModel
from searcher.core.ids import new_id
from searcher.core.time import UtcDateTime, format_utc, utc_now
from searcher.storage.repositories import Repositories

PUBLIC_EVENT_NAMES = frozenset(item.value for item in PublicEventName)


class CampaignEvent(SearcherModel):
    event_id: str = Field(default_factory=new_id)
    search_id: str
    state_version: int
    timestamp: UtcDateTime = Field(default_factory=utc_now)
    actor: str
    input_digests: list[str] = Field(default_factory=list)
    output_digests: list[str] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    predecessor: str | None = None
    error: str | None = None
    event_name: str
    payload: dict[str, object] = Field(default_factory=dict)


def append_event(repos: Repositories, event: CampaignEvent) -> CampaignEvent:
    """Insert-only. There is no update or delete path."""
    payload = event.model_dump(mode="json")
    payload["timestamp"] = format_utc(event.timestamp)
    repos.insert_event(payload)
    return event


def list_events(repos: Repositories, search_id: str) -> list[CampaignEvent]:
    return [CampaignEvent.model_validate(row) for row in repos.list_events(search_id)]


def event_chain_ok(events: list[CampaignEvent]) -> bool:
    predecessor: str | None = None
    for event in events:
        if event.predecessor != predecessor:
            return False
        predecessor = event.event_id
    return True


def is_public_event(name: str) -> bool:
    return name in PUBLIC_EVENT_NAMES


def numbered_public_events(
    repos: Repositories, search_id: str, *, after: int = 0
) -> list[tuple[int, CampaignEvent]]:
    """Campaign-local 1-based sequence over §25.4 events, for SSE Last-Event-ID."""
    out: list[tuple[int, CampaignEvent]] = []
    seq = 0
    for event in list_events(repos, search_id):
        if not is_public_event(event.event_name):
            continue
        seq += 1
        if seq > after:
            out.append((seq, event))
    return out


def public_payload(event: CampaignEvent) -> dict[str, Any]:
    return {
        "event": event.event_name,
        "search_id": event.search_id,
        "state_version": event.state_version,
        "timestamp": format_utc(event.timestamp),
        "payload": event.payload,
        "error": event.error,
    }
