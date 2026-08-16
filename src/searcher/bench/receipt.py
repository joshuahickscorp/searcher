"""Performance receipt written by the latency benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from searcher import CODE_VERSION, SCHEMA_VERSION
from searcher.core.policy import POLICY_VERSION
from searcher.core.time import format_utc, utc_now

TARGETS: dict[str, float] = {
    "ui_first_byte_ms": 200.0,
    "search_create_ms": 300.0,
    "first_progress_event_ms": 500.0,
    "first_candidate_ms_warm": 3000.0,
    "repeat_first_result_ms": 1000.0,
    "health_ms": 50.0,
    "capabilities_ms": 100.0,
}

STRUCTURAL_NOTE = (
    "Searcher answers a live campaign: it plans queries, fetches admitted sources, "
    "normalizes, clusters, matches, and checks liveness. A precomputed image index "
    "answers a lookup against work that already happened. Those are different "
    "operations. A cold live campaign cannot equal an index lookup. Repeat and "
    "overlapping searches can, because the warm local index avoids doing the same "
    "source work twice. This receipt records measured numbers on this host. "
    "It does not claim parity with a precomputed index."
)


def write_receipt(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "measured_at": format_utc(utc_now()),
        "code_version": CODE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "policy_version": POLICY_VERSION,
        "note": STRUCTURAL_NOTE,
        "targets_ms": TARGETS,
        **payload,
    }
    rendered = json.dumps(body, indent=2, sort_keys=True, default=str) + "\n"
    path.write_text(rendered, encoding="utf-8")
    return path
