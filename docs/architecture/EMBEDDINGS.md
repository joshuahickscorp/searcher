# Local embeddings

The backbone is DINOv2 ViT-S/14 (`facebookresearch.dinov2.vits14`), loaded
from a traced TorchScript file at `$SEARCHER_DATA_ROOT/models/embedding.pt`
(or `$SEARCHER_EMBEDDING_WEIGHTS`). Weights are prepared once by
`scripts/prepare_embedding_weights.py`. A search never downloads. Absent,
dummy, or unreadable weights report unavailable — availability is a
successful probe call, not file existence.

```text
uv sync --extra vision
uv run python scripts/prepare_embedding_weights.py
```

`import searcher` and the default capability probe stay torch-free. Asking
`embedding_capability(probe=True)` loads the module once, caches the
outcome, and only then may report `available=True`. Absent weights, or a
failed probe, `DENSE_FEATURES` is unavailable and `embed_png()` returns
`None`.

Cosine similarity is an observed pixel-level measurement. It feeds the existing
`embedding_similarity` cheap signal and a cited item-match evidence entry. It
is not a brand, authenticity, or Real-gate shortcut. Threshold, TPR/FPR, and
sample sizes live in `artifacts/searcher-match-calibration.receipt.json`.
The public retrieval figures live in
`artifacts/searcher-public-benchmark.receipt.json`.
