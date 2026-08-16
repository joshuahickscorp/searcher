"""Embedding gateway: absence, wiring, and (when weights exist) determinism."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tests.helpers_matching import make_candidate, make_hypothesis
from tests.support.offline_shop import tiny_png

from searcher.core.capabilities import CapabilityName
from searcher.matching.pipeline import match_candidate
from searcher.matching.types import EnrichedCandidate
from searcher.retrieval.broad import retrieve_broad
from searcher.retrieval.embeddings import (
    cosine_similarity,
    embed_png,
    embed_pngs,
    embedding_capability,
    find_local_weights,
    resolve_backend,
)


def test_absence_without_weights(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SEARCHER_EMBEDDING_WEIGHTS", raising=False)
    monkeypatch.setenv("SEARCHER_DATA_ROOT", str(tmp_path))
    assert find_local_weights() is None
    assert resolve_backend() is None
    record = embedding_capability()
    assert record.name is CapabilityName.DENSE_FEATURES
    assert record.available is False
    assert embed_png(tiny_png()) is None


def test_embed_pngs_matches_single_length_without_weights(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SEARCHER_EMBEDDING_WEIGHTS", raising=False)
    monkeypatch.setenv("SEARCHER_DATA_ROOT", str(tmp_path))
    pngs = [tiny_png(), tiny_png((9, 8, 7))]
    assert embed_pngs(pngs) == [None, None]
    assert embed_png(pngs[0]) is None


def test_cosine_of_unit_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_broad_and_match_use_embedding_score(monkeypatch: pytest.MonkeyPatch) -> None:
    from searcher.retrieval import embeddings as emb
    from searcher.retrieval.embeddings import EmbeddingBackend

    backend = EmbeddingBackend(
        identity="test-stub",
        revision="stub",
        weights_path="/tmp/does-not-exist.pt",
        authority_ceiling="OBSERVED-pixels",
    )
    ref_png = tiny_png((10, 20, 30))
    same_png = tiny_png((10, 20, 30))
    other_png = tiny_png((200, 10, 10))
    vectors = {
        ref_png: [1.0, 0.0, 0.0],
        same_png: [1.0, 0.0, 0.0],
        other_png: [0.0, 1.0, 0.0],
    }

    def fake_resolve() -> EmbeddingBackend:
        return backend

    def fake_embed(png: bytes, resolved: EmbeddingBackend | None = None) -> list[float] | None:
        del resolved
        return list(vectors.get(png, [0.0, 0.0, 1.0]))

    def fake_embed_pngs(
        pngs: list[bytes], resolved: EmbeddingBackend | None = None
    ) -> list[list[float] | None]:
        return [fake_embed(png, resolved) for png in pngs]

    monkeypatch.setattr(emb, "resolve_backend", fake_resolve)
    monkeypatch.setattr(emb, "embed_png", fake_embed)
    monkeypatch.setattr(emb, "embed_pngs", fake_embed_pngs)
    monkeypatch.setattr("searcher.retrieval.broad.resolve_backend", fake_resolve)
    monkeypatch.setattr("searcher.retrieval.broad.embed_pngs", fake_embed_pngs)
    monkeypatch.setattr("searcher.matching.pipeline.pair_similarity", lambda *a, **k: 1.0)

    hyp = make_hypothesis(category="garment")
    true_c, _ = make_candidate(candidate_id="true", title="WILLY CHAVARRIA long sleeve")
    other_c, _ = make_candidate(candidate_id="other", title="unrelated navy coat")
    result = retrieve_broad(
        candidates=[true_c, other_c],
        hypothesis=hyp,
        reference_signature=hyp.visual_signature,
        reference_pngs={"r": ref_png},
        candidate_pngs={"true": {"a": same_png}, "other": {"b": other_png}},
    )
    by_id = {hit.candidate.candidate_id: hit for hit in result.hits}
    assert by_id["true"].signals.embedding == pytest.approx(1.0)
    assert by_id["other"].signals.embedding == pytest.approx(0.0)
    assert by_id["true"].signals.recall_score > by_id["other"].signals.recall_score

    enriched = EnrichedCandidate(candidate=true_c, pngs={"a": tiny_png()})
    evidence = match_candidate(
        hypothesis=hyp,
        candidate=enriched,
        reference_pngs={"r": tiny_png()},
        reference_descriptors={},
    )
    cites = " ".join(evidence.explanation.support + evidence.global_visual.support)
    assert "embedding" in cites
    assert evidence.global_visual.fact_class.value == "OBSERVED"


def test_determinism_when_weights_present() -> None:
    if resolve_backend() is None:
        pytest.skip("local embedding weights are not installed")
    pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    os.environ.setdefault("SEARCHER_EMBEDDING_DEVICE", "cpu")
    png = tiny_png()
    first = embed_png(png)
    second = embed_png(png)
    assert first is not None
    assert first == second
    assert cosine_similarity(first, first) == pytest.approx(1.0)
    # A different raster must not be a perfect match.
    other = bytearray(png)
    other[-20] = (other[-20] + 40) % 256
    distant = embed_png(bytes(other))
    if distant is not None:
        assert cosine_similarity(first, distant) < 0.999
