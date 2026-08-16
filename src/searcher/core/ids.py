"""UUID generation, canonical encoding, and §10.4 idempotency keys."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from typing import Any


def new_id() -> str:
    return str(uuid.uuid4())


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_dumps(value: object) -> str:
    """Stable JSON for digests and idempotency keys."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_default,
    )


def _default(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(f"not JSON-canonicalizable: {type(value)!r}")


def idempotency_key(
    *,
    task_type: str,
    search_id: str,
    input_digests: Sequence[str],
    adapter_version: str,
    backend_version: str,
    policy_version: str,
    parameters: Mapping[str, Any] | None = None,
) -> str:
    """Derive the §10.4 key. Same inputs always produce the same key."""
    payload = {
        "task_type": task_type,
        "search_id": search_id,
        "input_digests": list(input_digests),
        "adapter_version": adapter_version,
        "backend_version": backend_version,
        "policy_version": policy_version,
        "parameters": dict(parameters) if parameters is not None else {},
    }
    return sha256_hex(canonical_dumps(payload).encode("utf-8"))
