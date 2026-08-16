"""Progress events into the Wave 1 append-only log."""

from __future__ import annotations

from typing import Any

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import PublicEventName


class SourceEvents:
    def __init__(self, controller: CampaignController, search_id: str) -> None:
        self.controller = controller
        self.search_id = search_id

    def emit(self, name: str, payload: dict[str, Any], *, error: str | None = None) -> None:
        self.controller.emit(
            self.search_id,
            name,
            payload=payload,
            actor="source_engine",
            error=error,
        )

    def source_start(self, source_id: str) -> None:
        self.emit(
            PublicEventName.SEARCH_PROGRESS.value, {"phase": "source_start", "source": source_id}
        )  # noqa: E501

    def query_dispatch(self, source_id: str, query: str) -> None:
        self.emit(
            PublicEventName.SEARCH_PROGRESS.value,
            {"phase": "query_dispatch", "source": source_id, "query": query},
        )

    def candidates_found(self, source_id: str, count: int) -> None:
        self.emit(
            PublicEventName.CANDIDATE_DISCOVERED.value,
            {"source": source_id, "count": count},
        )

    def page_fetched(self, source_id: str, url: str, outcome: str) -> None:
        self.emit(
            PublicEventName.SEARCH_PROGRESS.value,
            {"phase": "page_fetched", "source": source_id, "url": url, "outcome": outcome},
        )

    def coverage(self, source_id: str, outcome: str, pages: int) -> None:
        self.emit(
            PublicEventName.SEARCH_COVERAGE.value,
            {"source": source_id, "outcome": outcome, "pages": pages},
        )

    def blocked(self, source_id: str, outcome: str, basis: str) -> None:
        self.emit(
            PublicEventName.SEARCH_WARNING.value,
            {"source": source_id, "outcome": outcome, "basis": basis},
        )

    def complete(self, source_id: str, outcome: str) -> None:
        self.emit(
            PublicEventName.SEARCH_PROGRESS.value,
            {"phase": "source_complete", "source": source_id, "outcome": outcome},
        )
