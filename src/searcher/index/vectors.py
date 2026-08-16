"""Compact descriptors over stored listings. SQLite + numpy, no vector database."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from searcher.core.ids import sha256_hex

DESCRIPTOR_DIM = 64


def hashed_text_vector(terms: Sequence[str], *, dim: int = DESCRIPTOR_DIM) -> list[float]:
    """Deterministic bag-of-terms vector. Listing tokens are data, not instructions."""
    vec = np.zeros(dim, dtype=np.float32)
    for term in terms:
        if not term:
            continue
        bucket = int(sha256_hex(term.encode("utf-8"))[:8], 16) % dim
        vec[bucket] += 1.0
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return [float(x) for x in vec.tolist()]


def pack_descriptor(values: Sequence[float]) -> bytes:
    return np.asarray(list(values), dtype=np.float32).tobytes()


def unpack_descriptor(blob: bytes) -> list[float]:
    array = np.frombuffer(blob, dtype=np.float32)
    return [float(x) for x in array.tolist()]


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    a = np.asarray(list(left), dtype=np.float32)
    b = np.asarray(list(right), dtype=np.float32)
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)
