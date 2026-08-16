"""WAL-mode SQLite with exactly one writer, enforced in code."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from searcher.core.errors import ErrorClass, SearcherError


class Database:
    """One connection, WAL, foreign keys, a process-local write lock."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._in_write = False
        self._conn = sqlite3.connect(
            str(self.path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA synchronous=NORMAL")

    def raw(self) -> sqlite3.Connection:
        return self._conn

    def reader(self) -> sqlite3.Connection:
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            if self._in_write:
                yield self._conn
                return
            self._in_write = True
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                yield self._conn
                if self._conn.in_transaction:
                    self._conn.execute("COMMIT")
            except Exception:
                if self._conn.in_transaction:
                    self._conn.execute("ROLLBACK")
                raise
            finally:
                self._in_write = False

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def close(self) -> None:
        self._conn.close()

    def enforce_single_writer(self) -> None:
        if self._in_write:
            raise SearcherError(
                "a second writer attempted to enter a campaign transaction",
                error_class=ErrorClass.DATABASE,
            )
