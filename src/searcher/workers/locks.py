"""Process-local locks for objects the donor layers left unlocked."""

from __future__ import annotations

import threading
from typing import Any

# ContentStore's object index and hard-link zone have no lock. Concurrent
# puts of the same bytes raise FileExistsError / torn JSON.
STORE_LOCK = threading.RLock()


class LockedController:
    """Serialize runtime/event writes across concurrent source threads.

    The SQLite connection is already one-writer. This lock covers the
    read-modify-write on runtime_json and the event predecessor chain,
    which live above that connection.
    """

    def __init__(self, inner: Any) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_lock", threading.RLock())

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def set_runtime(self, search_id: str, **fields: object) -> None:
        with self._lock:
            merge = getattr(self._inner.repos, "merge_runtime", None)
            if callable(merge):
                merge(search_id, fields)
                return
            self._inner.set_runtime(search_id, **fields)

    def emit(self, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return self._inner.emit(*args, **kwargs)

    def store_receipt(self, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return self._inner.store_receipt(*args, **kwargs)

    def persist_usage(self, search_id: str) -> None:
        with self._lock:
            self._inner.persist_usage(search_id)
