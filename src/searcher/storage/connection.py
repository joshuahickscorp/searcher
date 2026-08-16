"""WAL-mode SQLite with exactly one writer, enforced in code."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from searcher.core.errors import ErrorClass, SearcherError


class SnapshotRow:
    """Copied statement values. Safe after the connection runs another query."""

    __slots__ = ("_map", "_vals")

    def __init__(self, row: sqlite3.Row) -> None:
        keys = list(row.keys())
        self._map = {key: row[key] for key in keys}
        self._vals = tuple(self._map[key] for key in keys)

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._vals[key]
        return self._map[key]

    def __contains__(self, key: object) -> bool:
        return key in self._map

    def keys(self) -> Iterator[str]:
        return iter(self._map)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._vals)

    def __len__(self) -> int:
        return len(self._vals)


class SnapshotCursor:
    """Rows materialized before Database.execute() releases the write lock."""

    __slots__ = ("_rows", "_index", "lastrowid", "rowcount", "description")

    def __init__(
        self,
        rows: list[SnapshotRow],
        *,
        lastrowid: int | None,
        rowcount: int,
        description: object,
    ) -> None:
        self._rows = rows
        self._index = 0
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self.description = description

    def fetchone(self) -> Any:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self) -> list[SnapshotRow]:
        rest = self._rows[self._index :]
        self._index = len(self._rows)
        return rest

    def fetchmany(self, size: int | None = None) -> list[SnapshotRow]:
        if size is None or size < 0:
            return self.fetchall()
        end = min(self._index + size, len(self._rows))
        chunk = self._rows[self._index : end]
        self._index = end
        return chunk

    def __iter__(self) -> Iterator[SnapshotRow]:
        return iter(self.fetchall())


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

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> SnapshotCursor:
        """Run a statement and copy every row before dropping the lock.

        sqlite3.Row aliases the live statement. Returning the raw cursor let a
        second thread reset that statement, so a later fetchone() saw NULL
        columns (intent_json=None) and the campaign went FAILED.
        """
        with self._lock:
            cur = self._conn.execute(sql, params)
            rows = [SnapshotRow(row) for row in cur.fetchall()]
            return SnapshotCursor(
                rows,
                lastrowid=cur.lastrowid,
                rowcount=cur.rowcount,
                description=cur.description,
            )

    def close(self) -> None:
        self._conn.close()

    def enforce_single_writer(self) -> None:
        if self._in_write:
            raise SearcherError(
                "a second writer attempted to enter a campaign transaction",
                error_class=ErrorClass.DATABASE,
            )
