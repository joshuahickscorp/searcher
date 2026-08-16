"""Process settings. Values come from the environment with safe relative defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from searcher import CODE_VERSION, SCHEMA_VERSION
from searcher.core.policy import POLICY_VERSION

_DEFAULT_DISK_MARGIN = 256 * 1024 * 1024
_DEFAULT_MAX_OBJECT = 50 * 1024 * 1024


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings. No user-home paths are baked in."""

    data_root: Path
    policy_version: str
    schema_version: str
    code_version: str
    disk_margin_bytes: int
    max_object_bytes: int
    step_delay_seconds: float
    fixtures_dir: Path | None
    migrations_dir: Path | None

    @property
    def db_path(self) -> Path:
        return self.data_root / "searcher.sqlite"

    @property
    def objects_root(self) -> Path:
        return self.data_root / "objects"

    @classmethod
    def from_env(cls, *, data_root: Path | str | None = None) -> Settings:
        root = (
            Path(data_root)
            if data_root is not None
            else Path(os.environ.get("SEARCHER_DATA_ROOT", "data"))
        )
        fixtures = os.environ.get("SEARCHER_FIXTURES_DIR")
        migrations = os.environ.get("SEARCHER_MIGRATIONS_DIR")
        delay_ms = _env_float("SEARCHER_STEP_DELAY_MS", 0.0)
        return cls(
            data_root=root,
            policy_version=os.environ.get("SEARCHER_POLICY_VERSION", POLICY_VERSION),
            schema_version=os.environ.get("SEARCHER_SCHEMA_VERSION", SCHEMA_VERSION),
            code_version=os.environ.get("SEARCHER_CODE_VERSION", CODE_VERSION),
            disk_margin_bytes=_env_int("SEARCHER_DISK_MARGIN_BYTES", _DEFAULT_DISK_MARGIN),
            max_object_bytes=_env_int("SEARCHER_MAX_OBJECT_BYTES", _DEFAULT_MAX_OBJECT),
            step_delay_seconds=max(0.0, delay_ms / 1000.0),
            fixtures_dir=Path(fixtures) if fixtures else None,
            migrations_dir=Path(migrations) if migrations else None,
        )

    def ensure_data_root(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
