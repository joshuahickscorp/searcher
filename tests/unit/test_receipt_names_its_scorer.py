"""A benchmark number must say which scorer produced it.

The round-5 grader measured recall@1 0.914286 where the committed receipt said
0.771429, and the two looked like the same measurement disagreeing. They were
not: the embedding weights are not in the repository, so an extracted tree
falls back to the perceptual-hash scorer and reports numbers in the same
fields. A receipt that does not name its scorer cannot be reproduced, and
cannot be contradicted either.
"""

from __future__ import annotations

from typing import Any

import pytest
from benchmark.receipt import _scorer_identity


def test_scorer_identity_names_the_backend_when_present() -> None:
    identity = _scorer_identity()
    assert "available" in identity
    if identity["available"]:
        assert identity["identity"]
        assert identity["identity"] != "unknown"


def test_scorer_identity_says_plainly_when_there_is_no_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import searcher.retrieval.embeddings as embeddings

    monkeypatch.setattr(embeddings, "resolve_backend", lambda: None)
    identity: dict[str, Any] = _scorer_identity()
    assert identity["available"] is False
    assert "fallback" in identity["identity"]
    # The reason must warn that the numbers are not comparable, not merely note
    # that weights were absent.
    assert "not comparable" in identity["reason"]


def test_committed_receipt_carries_a_scorer() -> None:
    import json
    from pathlib import Path

    path = Path("artifacts/searcher-public-benchmark.receipt.json")
    if not path.is_file():
        pytest.skip("benchmark receipt has not been generated on this host")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    assert "scorer" in receipt, "a published benchmark receipt must name its scorer"
    assert "available" in receipt["scorer"]
