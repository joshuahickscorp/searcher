"""Numbered .sql migrations. No ORM, no Alembic."""

from __future__ import annotations

import os
from pathlib import Path

from searcher.core.time import format_utc, utc_now
from searcher.storage.connection import Database


def migrations_dir(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    env = os.environ.get("SEARCHER_MIGRATIONS_DIR")
    if env:
        return Path(env)
    cwd = Path.cwd() / "migrations"
    if cwd.is_dir():
        return cwd
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "migrations"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("cannot locate migrations/")


def migrate(db: Database | Path | str, directory: Path | None = None) -> list[str]:
    if not isinstance(db, Database):
        database = Database(db)
        close = True
    else:
        database = db
        close = False
    applied: list[str] = []
    try:
        folder = migrations_dir(directory)
        files = sorted(p for p in folder.glob("*.sql") if p.name[:3].isdigit())
        conn = database.raw()
        # executescript() issues COMMIT first, so do not wrap it in BEGIN.
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL)"
        )
        existing = {
            str(row["name"])
            for row in conn.execute("SELECT name FROM schema_migrations").fetchall()
        }
        for path in files:
            if path.name in existing:
                continue
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                (path.name, format_utc(utc_now())),
            )
            applied.append(path.name)
        return applied
    finally:
        if close:
            database.close()
