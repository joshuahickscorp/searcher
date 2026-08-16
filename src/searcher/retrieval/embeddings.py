"""Optional learned global embeddings behind the §26.8 model gateway.

Activates only when weights are already present locally. Never downloads.
When absent the capability is blocked and cheap tiers still produce a result.

Backbone: torchvision ResNet50 IMAGENET1K_V2, penultimate GAP features,
L2-normalised cosine. Torch is imported only inside the functions that
need it so `import searcher` and the capability probe stay torch-free.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from searcher.core.embedding_gateway import (
    BACKBONE_IDENTITY,
    FEATURE_DIM,
    OPERATING_THRESHOLD,
    TARGET_FPR,
    EmbeddingBackend,
    embedding_capability,
    find_local_weights,
    resolve_backend,
)
from searcher.core.ids import sha256_hex

# Calibrated on live kind.co.jp pairs; see artifacts/searcher-match-calibration.receipt.json.
_RESIZE = 256
_CROP = 224
_MEAN = (0.485, 0.456, 0.406)
_STD = (0.229, 0.224, 0.225)

_MODEL: tuple[str, str, Any] | None = None
_VEC_CACHE: dict[tuple[str, str], list[float]] = {}
_LAST_EMBED_MS = 0.0

__all__ = [
    "BACKBONE_IDENTITY",
    "FEATURE_DIM",
    "OPERATING_THRESHOLD",
    "TARGET_FPR",
    "EmbeddingBackend",
    "cosine_similarity",
    "embed_png",
    "embedding_capability",
    "find_local_weights",
    "last_embed_latency_ms",
    "max_pairwise_cosine",
    "pair_similarity",
    "resolve_backend",
]


def last_embed_latency_ms() -> float:
    return _LAST_EMBED_MS


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return float(sum(a * b for a, b in zip(left, right, strict=True)))


def max_pairwise_cosine(
    references: list[list[float] | None],
    candidates: list[list[float] | None],
) -> float | None:
    best: float | None = None
    for ref in references:
        if ref is None:
            continue
        for cand in candidates:
            if cand is None:
                continue
            score = cosine_similarity(ref, cand)
            best = score if best is None else max(best, score)
    return best


def pair_similarity(
    reference_pngs: dict[str, bytes],
    candidate_pngs: dict[str, bytes],
    backend: EmbeddingBackend | None = None,
) -> float | None:
    resolved = backend or resolve_backend()
    if resolved is None or not reference_pngs or not candidate_pngs:
        return None
    refs = [embed_png(png, resolved) for png in reference_pngs.values()]
    cands = [embed_png(png, resolved) for png in candidate_pngs.values()]
    return max_pairwise_cosine(refs, cands)


def _select_device(torch: Any) -> Any:
    forced = os.environ.get("SEARCHER_EMBEDDING_DEVICE", "").strip().lower()
    if forced == "cpu":
        return torch.device("cpu")
    mps_ok = bool(getattr(getattr(torch, "backends", None), "mps", None)) and bool(
        torch.backends.mps.is_available()
    )
    if forced == "mps":
        return torch.device("mps") if mps_ok else torch.device("cpu")
    if mps_ok:
        return torch.device("mps")
    return torch.device("cpu")


def _load_state_dict(torch: Any, path: Path) -> dict[str, Any]:
    blob = torch.load(path, map_location="cpu", weights_only=True)
    if isinstance(blob, dict) and "state_dict" in blob and isinstance(blob["state_dict"], dict):
        return blob["state_dict"]
    if isinstance(blob, dict):
        return blob
    raise TypeError(f"embedding weights at {path} are not a state dict")


def _get_model(path: Path) -> tuple[Any, Any] | None:
    global _MODEL
    device_key = os.environ.get("SEARCHER_EMBEDDING_DEVICE", "").strip().lower() or "auto"
    cache_key = f"{path}:{device_key}:{path.stat().st_mtime_ns}"
    if _MODEL is not None and _MODEL[0] == cache_key:
        return _MODEL[1], _MODEL[2]
    try:
        import torch
        from torchvision.models import resnet50
    except ImportError:
        return None
    try:
        state = _load_state_dict(torch, path)
        model = resnet50(weights=None)
        model.load_state_dict(state)
        model.fc = torch.nn.Identity()
        model.eval()
        device = _select_device(torch)
        model.to(device)
    except Exception:
        return None
    _MODEL = (cache_key, model, device)
    return model, device


def _to_tensor(png: bytes, torch: Any, device: Any) -> Any:
    from io import BytesIO

    import numpy as np
    from PIL import Image

    image = Image.open(BytesIO(png)).convert("RGB")
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("empty image")
    if width < height:
        new_w = _RESIZE
        new_h = max(1, int(round(height * _RESIZE / width)))
    else:
        new_h = _RESIZE
        new_w = max(1, int(round(width * _RESIZE / height)))
    image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
    left = max(0, (new_w - _CROP) // 2)
    top = max(0, (new_h - _CROP) // 2)
    image = image.crop((left, top, left + _CROP, top + _CROP))
    if image.size != (_CROP, _CROP):
        image = image.resize((_CROP, _CROP), Image.Resampling.BILINEAR)
    arr = np.asarray(image, dtype=np.float32) / 255.0
    mean = np.asarray(_MEAN, dtype=np.float32)
    std = np.asarray(_STD, dtype=np.float32)
    arr = (arr - mean) / std
    tensor = torch.from_numpy(np.ascontiguousarray(arr.transpose(2, 0, 1)))
    return tensor.unsqueeze(0).to(device)


def embed_png(png: bytes, backend: EmbeddingBackend | None = None) -> list[float] | None:
    """Return a unit vector when a local backend can load. Never downloads."""
    global _LAST_EMBED_MS
    started = time.perf_counter()
    resolved = backend or resolve_backend()
    if resolved is None or not png:
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return None
    path = Path(resolved.weights_path)
    digest = sha256_hex(png)
    cache_key = (str(path), digest)
    held = _VEC_CACHE.get(cache_key)
    if held is not None:
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return list(held)
    loaded = _get_model(path)
    if loaded is None:
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return None
    model, device = loaded
    try:
        import torch
    except ImportError:
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return None
    try:
        tensor = _to_tensor(png, torch, device)
        with torch.inference_mode():
            feats = model(tensor)
            feats = torch.nn.functional.normalize(feats, p=2, dim=1)
            vector = feats.squeeze(0).detach().cpu().tolist()
    except Exception:
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return None
    if not isinstance(vector, list) or not vector:
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return None
    out = [float(v) for v in vector]
    if len(_VEC_CACHE) > 512:
        _VEC_CACHE.clear()
    _VEC_CACHE[cache_key] = out
    _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
    return list(out)
