# Searcher public benchmark report

Measured by `uv run python -m benchmark.run --all` on 2026-08-16.
This is a measurement receipt, not a claim entitlement. It does not
authorize a public accuracy sentence in CLAIMS.md.

Regenerate: `uv run python -m benchmark.run --all`

Receipt: `artifacts/searcher-public-benchmark.receipt.json`
Evidence board: `artifacts/benchmark/evidence-board.html`
Split authority: `fixtures/benchmark/splits.json`
Method: `docs/SEARCHER_BENCHMARK_METHOD.md`

Host `Mac-Studio`. git `e1716058a93a31c6252f6f54867beb817e30b25a`.
code `0.1.0`. policy `provisional-1`.

## Authority

Calibration hash `ad8f4851f79c66338c1a2430b7fee1242d77e8f940b57faa9fa83a793655c5f1`.
Held-out hash `2d0e2ae65f6991595fb3c0b2917d20a4e358c159df9b1ca9c462de7ea1595d55`.
Hidden evaluation: absent (not authorized).

KIND photographs are the cached `fixtures/known_item_kind` set
(shop.kind.co.jp, fetch date in `pack.json`). Hard-negative cases are
project-generated synthetic shoes. No new marketplace was scraped.
No operator photograph was used.

## Retrieval (held-out)

Scorer: `searcher.cheap_visual.ahash_colour` (no local DINOv2 weights
on this host). Closed-set: five KIND listings, gallery image 1 versus
query image 2, seven degradations. n = 35.

| set | n | recall@1 | recall@5 | recall@10 | MRR |
|---|---:|---:|---:|---:|---:|
| overall | 35 | 0.914 | 1.000 | 1.000 | 0.940 |
| pristine | 5 | 1.000 | 1.000 | 1.000 | 1.000 |
| blur | 5 | 1.000 | 1.000 | 1.000 | 1.000 |
| heavy_blur | 5 | 1.000 | 1.000 | 1.000 | 1.000 |
| crop | 5 | 0.400 | 1.000 | 1.000 | 0.583 |
| small | 5 | 1.000 | 1.000 | 1.000 | 1.000 |
| recompressed | 5 | 1.000 | 1.000 | 1.000 | 1.000 |
| phone_snapshot | 5 | 1.000 | 1.000 | 1.000 | 1.000 |

The three misses are all `crop`. Including the known-item target
`kind:8001001141404:crop`, which ranked 3 (top was `kind:8001001141480`).
Gallery size is 5, so recall@10 equals recall@gallery.

## Bucket decisions (held-out)

Constructed labels on seven synthetic cases. Not authenticity accuracy.

| label | precision | recall |
|---|---:|---:|
| real | 1.0 | 1.0 |
| possibly_real | 1.0 | 1.0 |
| replica | 1.0 | 1.0 |
| hidden | 1.0 | 1.0 |

Confusion is diagonal. **False Real: 0 / 7** (0 / 6 labelled-not-Real).

## Calibration

20 pairs on the calibration KIND listings. Shipped threshold 0.86
(from `artifacts/searcher-match-calibration.receipt.json`) sits in
bin `[0.8, 0.9]` (n=3, positive_rate=0.667). It was not refit.

0.86 is a DINOv2 cosine gate. This host scored with cheap visual
signals, so the line is the policy point, not a fit on this histogram.
`dinov2_score_curve` is listed under `not_computed`.

## Operational

Same receipt as the quality numbers.

- wall per campaign: 0.235 s
- fetches per campaign: 0
- cache hit rate: 1.0 (authorized fixture cache)
- images per second: 148.1 (209 images in 1.411 s)

## Live recall finding (not a target)

`artifacts/searcher-adversarial-recall.receipt.json`: 0 / 21 on three
KIND URLs that are not in the cached fixture pack. Every trial finished
COMPLETE / coverage exhausted in ~2 s with empty result lists. That is
a discovery-coverage finding, not a ranking score.

## What this does not cover

Hidden evaluation. Live open-set retrieval. Authenticity accuracy.
Conventional-search comparison. Operator photographs. New marketplace
fetches. Recall@20, NDCG, colourway accuracy, multilingual retrieval.
Any claim that Searcher is better than another engine.
