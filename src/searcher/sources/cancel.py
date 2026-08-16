"""Cooperative cancel for a source run. Every await/loop checks this."""

from __future__ import annotations

import threading

from searcher.campaigns.cancellation import CancellationController
from searcher.core.errors import CancelledError


class RunCancel:
    def __init__(
        self,
        search_id: str,
        campaign: CancellationController | None = None,
    ) -> None:
        self.search_id = search_id
        self.campaign = campaign
        self._local = threading.Event()

    def request(self) -> None:
        self._local.set()
        if self.campaign is not None:
            self.campaign.request(self.search_id)

    def is_cancelled(self) -> bool:
        if self._local.is_set():
            return True
        if self.campaign is not None:
            return self.campaign.is_cancelled(self.search_id)
        return False

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise CancelledError("source run cancelled", search_id=self.search_id)
