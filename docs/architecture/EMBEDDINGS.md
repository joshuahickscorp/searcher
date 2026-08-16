# Local embeddings

Searcher loads a local ResNet50 (`IMAGENET1K_V2`) only when the operator has
already written weights to `$SEARCHER_DATA_ROOT/models/embedding.pt` (or
`$SEARCHER_EMBEDDING_WEIGHTS`). A search never downloads.

```text
uv sync --extra vision
uv run python scripts/prepare_embedding_weights.py
```

`import searcher` and the capability probe stay torch-free. Absent weights, the
pipeline is unchanged: `DENSE_FEATURES` is unavailable and `embed_png()` returns
`None`.

Cosine similarity is an observed pixel-level measurement. It feeds the existing
`embedding_similarity` cheap signal and a cited item-match evidence entry. It
is not a brand, authenticity, or Real-gate shortcut. Threshold, TPR/FPR, and
sample sizes live in `artifacts/searcher-match-calibration.receipt.json`.
