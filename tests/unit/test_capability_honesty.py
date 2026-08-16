"""DENSE_FEATURES is available only after a real probe call succeeds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from tests.support.offline_shop import tiny_png

from searcher.core.capabilities import CapabilityName
from searcher.core.embedding_gateway import (
    clear_embedding_probe_cache,
    embedding_capability,
    find_local_weights,
)


def _point_at(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setenv("SEARCHER_EMBEDDING_WEIGHTS", str(path))
    monkeypatch.delenv("SEARCHER_DATA_ROOT", raising=False)
    clear_embedding_probe_cache()


def _try_torch() -> Any | None:
    try:
        import torch
    except ImportError:
        return None
    return torch


def _write_tiny_script(path: Path, torch: Any) -> None:
    class Tiny(torch.nn.Module):  # type: ignore[name-defined]
        def forward(self, x: Any) -> Any:
            return x.mean(dim=(2, 3))

    traced = torch.jit.trace(Tiny(), torch.zeros(1, 3, 224, 224))
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.jit.save(traced, str(path))


def test_dummy_weights_are_not_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "models" / "embedding.pt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"garbage!")
    _point_at(monkeypatch, path)
    assert find_local_weights() == path.resolve()
    unprobed = embedding_capability()
    assert unprobed.name is CapabilityName.DENSE_FEATURES
    assert unprobed.available is not True
    probed = embedding_capability(probe=True)
    assert probed.available is not True
    assert probed.available is False
    try:
        from searcher.retrieval.embeddings import embed_png
    except ImportError:
        return
    assert embed_png(tiny_png()) is None


def test_working_weights_are_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "models" / "embedding.pt"
    torch = _try_torch()
    if torch is not None:
        _write_tiny_script(path, torch)
        _point_at(monkeypatch, path)
        record = embedding_capability(probe=True)
    else:
        path.parent.mkdir(parents=True)
        path.write_bytes(b"x" * 64)
        _point_at(monkeypatch, path)
        monkeypatch.setattr(
            "searcher.core.embedding_gateway._run_weights_probe",
            lambda _path: True,
        )
        record = embedding_capability(probe=True)
    assert record.name is CapabilityName.DENSE_FEATURES
    assert record.available is True


def test_unprobed_file_is_unknown_not_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "embedding.pt"
    path.write_bytes(b"not-a-model")
    _point_at(monkeypatch, path)
    record = embedding_capability()
    assert record.available is False
    assert "unknown" in record.notes.lower()
