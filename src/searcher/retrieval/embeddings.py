"""Optional learned global embeddings behind the §26.8 model gateway.

Activates only when weights are already present locally. Never downloads.
When absent the capability is blocked and cheap tiers still produce a result.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from searcher import SCHEMA_VERSION
from searcher.core.capabilities import CapabilityName, CapabilityRecord, CapabilityStability


@dataclass(frozen=True, slots=True)
class EmbeddingBackend:
    identity: str
    revision: str
    weights_path: str
    authority_ceiling: str = "local-embedding"


def _candidate_weight_paths() -> list[Path]:
    env = os.environ.get("SEARCHER_EMBEDDING_WEIGHTS", "").strip()
    paths: list[Path] = []
    if env:
        paths.append(Path(env))
    root = os.environ.get("SEARCHER_DATA_ROOT", "data")
    paths.append(Path(root) / "models" / "embedding.pt")
    paths.append(Path(root) / "models" / "clip.pt")
    return paths


def find_local_weights() -> Path | None:
    for path in _candidate_weight_paths():
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def resolve_backend() -> EmbeddingBackend | None:
    path = find_local_weights()
    if path is None:
        return None
    return EmbeddingBackend(
        identity="local-embedding",
        revision=path.name,
        weights_path=str(path),
        authority_ceiling="local-embedding",
    )


def embedding_capability() -> CapabilityRecord:
    backend = resolve_backend()
    if backend is None:
        return CapabilityRecord(
            name=CapabilityName.DENSE_FEATURES,
            available=False,
            stability=CapabilityStability.UNAVAILABLE,
            dependency=None,
            resource_cost="none",
            authority_ceiling="none",
            schema_version=SCHEMA_VERSION,
            notes=(
                "No local embedding weights. Promotion through the learned path "
                "is blocked. Free and classical tiers remain available."
            ),
        )
    return CapabilityRecord(
        name=CapabilityName.DENSE_FEATURES,
        available=True,
        stability=CapabilityStability.EXPERIMENTAL,
        dependency=backend.identity,
        resource_cost="cpu-embedding",
        authority_ceiling=backend.authority_ceiling,
        schema_version=SCHEMA_VERSION,
        notes=f"local weights at {backend.revision}; no download performed",
    )


def embed_png(png: bytes, backend: EmbeddingBackend | None = None) -> list[float] | None:
    """Return a vector only when a local backend is configured.

    This wave does not ship or load weights. The function exists so the
    gateway surface is real: absent weights → None, never a fabricated CLIP.
    """
    resolved = backend or resolve_backend()
    if resolved is None:
        return None
    del png
    return None
