"""Documents must not assert a capability state the code contradicts."""

from __future__ import annotations

from pathlib import Path

from searcher.core.embedding_gateway import BACKBONE_IDENTITY

ROOT = Path(__file__).resolve().parents[2]

# Old sentences that were false when the red-team report landed. Reverting a
# document to any of these must fail this test.
_FORBIDDEN: list[tuple[str, str]] = [
    ("ARCHITECTURE.md", "discovery is not wired into that process"),
    ("ARCHITECTURE.md", "They are not invoked by `scripts/run_api.sh`"),
    ("CLAIMS.md", "Matching in this tree is classical."),
    ("CLAIMS.md", "that the engine has a learned visual backbone"),
    ("LIMITATIONS.md", "No learned visual backbone."),
    ("LIMITATIONS.md", "No public benchmark has been run."),
    ("docs/architecture/EMBEDDINGS.md", "local ResNet50"),
    ("docs/architecture/API.md", "this version does not load it"),
    ("web/index.html", "the current benchmark"),
]

_REQUIRED: list[tuple[str, str]] = [
    ("docs/architecture/EMBEDDINGS.md", "DINOv2"),
    ("docs/architecture/EMBEDDINGS.md", "prepare_embedding_weights.py"),
    ("ARCHITECTURE.md", "SEARCHER_LIVE_DISCOVERY"),
    ("CLAIMS.md", "DINOv2"),
    ("LIMITATIONS.md", "recall@1 0.771"),
    ("docs/architecture/API.md", "DINOv2"),
    ("web/index.html", "recall@1 0.771"),
]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_run_api_enables_live_discovery() -> None:
    script = _read("scripts/run_api.sh")
    assert "SEARCHER_LIVE_DISCOVERY" in script
    assert "${SEARCHER_LIVE_DISCOVERY:-1}" in script


def test_code_backbone_is_dinov2() -> None:
    assert BACKBONE_IDENTITY == "facebookresearch.dinov2.vits14"


def test_documents_do_not_assert_contradicted_capability_states() -> None:
    for rel, phrase in _FORBIDDEN:
        text = _read(rel)
        assert phrase not in text, f"{rel} still claims {phrase!r}"


def test_documents_state_the_shipped_capability() -> None:
    for rel, phrase in _REQUIRED:
        text = _read(rel)
        assert phrase in text, f"{rel} is missing {phrase!r}"


def test_benchmark_receipt_exists_and_matches_cited_figures() -> None:
    import json

    receipt = json.loads(
        (ROOT / "artifacts/searcher-public-benchmark.receipt.json").read_text(encoding="utf-8")
    )
    overall = receipt["retrieval"]["overall"]
    assert overall["n"] == 35
    assert round(float(overall["recall_at_1"]), 3) == 0.771
    assert float(overall["recall_at_5"]) == 1.0
    assert round(float(overall["mrr"]), 3) == 0.867
    assert int(receipt["buckets"]["false_real"]["count"]) == 0
