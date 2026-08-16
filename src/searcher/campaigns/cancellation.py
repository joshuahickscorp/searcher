"""§10.5 cancellation: stop new work, bounded cleanup, persist, retain evidence."""

from __future__ import annotations

import threading
import time

from searcher.contracts.enums import CampaignState, TerminalVerdict
from searcher.core.errors import CancelledError


class CancellationController:
    def __init__(self) -> None:
        self._flags: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def flag(self, search_id: str) -> threading.Event:
        with self._lock:
            event = self._flags.get(search_id)
            if event is None:
                event = threading.Event()
                self._flags[search_id] = event
            return event

    def request(self, search_id: str) -> None:
        self.flag(search_id).set()

    def is_cancelled(self, search_id: str) -> bool:
        return self.flag(search_id).is_set()

    def raise_if_cancelled(self, search_id: str) -> None:
        if self.is_cancelled(search_id):
            raise CancelledError("campaign cancelled", search_id=search_id)

    def bounded_cleanup(self, seconds: float) -> None:
        """Workers get a bounded interval to close resources. Wave 1 has none."""
        if seconds > 0:
            time.sleep(min(seconds, 5.0))

    def terminal_for(self) -> tuple[CampaignState, TerminalVerdict]:
        return CampaignState.CANCELLED, TerminalVerdict.CANCELLED
