"""Weight-path resolution for the §26.8 embedding gateway.

Kept out of searcher.retrieval so the capability probe can stay cheap and
must not import torch or close a retrieval ↔ reference ↔ probe cycle.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from searcher import SCHEMA_VERSION
from searcher.core.capabilities import CapabilityName, CapabilityRecord, CapabilityStability

# Pair-level operating point at FPR ≤ 0.05 on the kind.co.jp calibration set.
# ImageNet ResNet50 is a pixel measurement, not an item classifier: same-listing
# views that do not overlap can score below this, and similar other garments can
# score near it. See artifacts/searcher-match-calibration.receipt.json.
OPERATING_THRESHOLD = 0.94
TARGET_FPR = 0.05
BACKBONE_IDENTITY = "torchvision.resnet50.IMAGENET1K_V2"
FEATURE_DIM = 2048


@dataclass(frozen=True, slots=True)
class EmbeddingBackend:
    identity: str
    revision: str
    weights_path: str
    authority_ceiling: str = "OBSERVED-pixels"


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


def _metadata_path(weights: Path) -> Path:
    return Path(str(weights) + ".json")


def _read_identity(path: Path) -> str:
    meta = _metadata_path(path)
    if meta.is_file():
        try:
            payload = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            identity = payload.get("identity")
            if isinstance(identity, str) and identity.strip():
                return identity.strip()
    if path.name == "embedding.pt":
        return BACKBONE_IDENTITY
    return "local-embedding"


def resolve_backend() -> EmbeddingBackend | None:
    path = find_local_weights()
    if path is None:
        return None
    return EmbeddingBackend(
        identity=_read_identity(path),
        revision=path.name,
        weights_path=str(path),
        authority_ceiling="OBSERVED-pixels",
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
        notes=(
            f"local weights at {backend.revision} ({backend.identity}); "
            "torch loaded lazily at embed time; no download performed"
        ),
    )
