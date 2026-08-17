# Searcher benchmark method

Bible §39 name. Draws from `docs/SEARCHER_BENCHMARK_METHOD.md`.
That file is the protocol. This file is the §39 binding.

The method implements Bible §31 as far as authorized data allows.
It measures. It does not retune a threshold and it does not entitle
a public accuracy claim.

## Command

```bash
uv run python -m benchmark.run --all
```

Same command as `./scripts/run_benchmark.sh` and
`uv run python -m benchmark --all`. One process writes
`artifacts/searcher-public-benchmark.receipt.json` and
`artifacts/benchmark/evidence-board.html`.

Split authority: `fixtures/benchmark/splits.json`.
`tests/unit/test_benchmark_splits.py` fails if any identifier
appears in both calibration and held-out. There is no authorized
hidden-evaluation set.

Threshold operating point (not refit by `--all`):

```bash
uv run python -m benchmark.threshold
```

writes `artifacts/searcher-threshold.receipt.json`.

## Dataset authority

Only images the project is already permitted to hold:

| Family | Where | Permission |
|---|---|---|
| KIND listings | `fixtures/known_item_kind` | Cached public product photographs from `shop.kind.co.jp`. KIND is admitted for GET product/collection. Fetch date is in `pack.json`. This run does not fetch new KIND photographs. |
| Hard-negative cases | `searcher.matching.synth` + `fixtures/hard_negatives` | Project-generated synthetic shoe diagrams. Labels are constructed from the recipe, not a professional authenticity judgment. |

No new marketplace is scraped. No operator photograph is included.

## Retrieval protocol

Closed-set listing retrieval on the KIND fixtures of the split
under test. Gallery: local image index 1. Query: local image index
2 under seven degradations (pristine, blur, heavy_blur, crop,
small, recompressed, phone_snapshot). Ranker: DINOv2 ViT-S/14
cosine when local weights load; otherwise cheap visual signals
(average hash + colour histogram). The receipt names the scorer.

Metrics: recall@1, recall@5, recall@10, MRR; overall and per
degradation. Recall@20 is not computed: the authorized gallery is
smaller than 20.

## Bucket protocol

`searcher.ranking.pipeline.judge_candidates` on the constructed
hard-negative cases of the held-out split, then
`published_public_bucket`. A false Real is a case whose constructed
label is not Real that the engine published as Real.

This is not an authenticity-accuracy claim.

## Calibration

Pair curve on calibration KIND listings only. The shipped
threshold 0.86 is taken from
`artifacts/searcher-match-calibration.receipt.json` and is not
refit.

That calibration receipt's headline backbone comparison is **not
reproducible** from this repository. Its own
`reproducibility.status` says so. The pair threshold it recorded
does not hold on the splits committed here: see
`artifacts/searcher-threshold.receipt.json`.

## What this benchmark does not cover

Hidden evaluation. Live open-set marketplace retrieval.
Authenticity accuracy. Conventional-search comparison (Bible
§31.8). Operator photographs. New marketplace fetches. Recall@20,
NDCG, colourway accuracy, multilingual retrieval. Any claim that
Searcher is better than another engine.

If a metric cannot be computed, the receipt names it under
`not_computed`.
