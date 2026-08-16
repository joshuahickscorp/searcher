"""Optional learned global embeddings behind the §26.8 model gateway.

Activates only when weights are already present locally. Never downloads.
When absent the capability is blocked and cheap tiers still produce a result.

Backbone: DINOv2 ViT-S/14 CLS token, L2-normalised cosine, loaded from a
traced TorchScript file. Torch is imported only inside the functions that
need it so `import searcher` and the capability probe stay torch-free.
"""

from __future__ import annotations

import os
import time
import warnings
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
    "embed_pngs",
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
    refs = embed_pngs(list(reference_pngs.values()), resolved)
    cands = embed_pngs(list(candidate_pngs.values()), resolved)
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


def _get_model(path: Path) -> tuple[Any, Any] | None:
    global _MODEL
    device_key = os.environ.get("SEARCHER_EMBEDDING_DEVICE", "").strip().lower() or "auto"
    cache_key = f"{path}:{device_key}:{path.stat().st_mtime_ns}"
    if _MODEL is not None and _MODEL[0] == cache_key:
        return _MODEL[1], _MODEL[2]
    try:
        import torch
    except ImportError:
        return None
    try:
        # A traced TorchScript module: the runtime needs torch and this file,
        # never torch.hub and never the network.
        device = _select_device(torch)
        jit_load: Any = torch.jit.load  # torch.jit is untyped for mypy
        with warnings.catch_warnings():
            # torch 2.13 deprecates torch.jit.load in favour of torch.export.
            # Callers run under -W error, and a library's deprecation notice is
            # not their failure.
            # ponytail: TorchScript still loads; move to torch.export when the
            # traced module is regenerated.
            warnings.simplefilter("ignore", DeprecationWarning)
            model = jit_load(str(path), map_location=device)
        model.eval()
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


def embed_pngs(
    pngs: list[bytes], backend: EmbeddingBackend | None = None
) -> list[list[float] | None]:
    """Embed many images in one forward pass on the existing device."""
    global _LAST_EMBED_MS
    started = time.perf_counter()
    resolved = backend or resolve_backend()
    results: list[list[float] | None] = [None] * len(pngs)
    if resolved is None or not pngs:
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return results
    path = Path(resolved.weights_path)
    loaded = _get_model(path)
    if loaded is None:
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return results
    model, device = loaded
    try:
        import torch
    except ImportError:
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return results
    miss_idx: list[int] = []
    miss_tensors: list[Any] = []
    for index, png in enumerate(pngs):
        if not png:
            continue
        cache_key = (str(path), sha256_hex(png))
        held = _VEC_CACHE.get(cache_key)
        if held is not None:
            results[index] = list(held)
            continue
        try:
            miss_tensors.append(_to_tensor(png, torch, device))
            miss_idx.append(index)
        except Exception:
            results[index] = None
    if miss_tensors:
        try:
            batch = torch.cat(miss_tensors, dim=0)
            with torch.inference_mode():
                feats = model(batch)
                feats = torch.nn.functional.normalize(feats, p=2, dim=1)
            cpu = feats.detach().cpu()
            for offset, index in enumerate(miss_idx):
                vector = cpu[offset].tolist()
                if not isinstance(vector, list) or not vector:
                    continue
                out = [float(v) for v in vector]
                if len(_VEC_CACHE) > 512:
                    _VEC_CACHE.clear()
                _VEC_CACHE[(str(path), sha256_hex(pngs[index]))] = out
                results[index] = list(out)
        except Exception:
            for index in miss_idx:
                if results[index] is None:
                    results[index] = _embed_one(pngs[index], resolved)
    _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
    return results


def _embed_one(png: bytes, resolved: EmbeddingBackend) -> list[float] | None:
    """Single-image fallback used only when a batch forward fails."""
    path = Path(resolved.weights_path)
    cache_key = (str(path), sha256_hex(png))
    held = _VEC_CACHE.get(cache_key)
    if held is not None:
        return list(held)
    loaded = _get_model(path)
    if loaded is None:
        return None
    model, device = loaded
    try:
        import torch
    except ImportError:
        return None
    try:
        tensor = _to_tensor(png, torch, device)
        with torch.inference_mode():
            feats = model(tensor)
            feats = torch.nn.functional.normalize(feats, p=2, dim=1)
            vector = feats.squeeze(0).detach().cpu().tolist()
    except Exception:
        return None
    if not isinstance(vector, list) or not vector:
        return None
    out = [float(v) for v in vector]
    if len(_VEC_CACHE) > 512:
        _VEC_CACHE.clear()
    _VEC_CACHE[cache_key] = out
    return list(out)


def embed_png(png: bytes, backend: EmbeddingBackend | None = None) -> list[float] | None:
    """Return a unit vector when a local backend can load. Never downloads."""
    if not png:
        global _LAST_EMBED_MS
        started = time.perf_counter()
        _LAST_EMBED_MS = (time.perf_counter() - started) * 1000.0
        return None
    return embed_pngs([png], backend)[0]
