# Searcher public benchmark report

Bible §39 name. The numbers in this file are the committed receipt
`artifacts/searcher-public-benchmark.receipt.json`. Command:

```bash
uv run python -m benchmark.run --all
```

`docs/SEARCHER_PUBLIC_BENCHMARK_REPORT.md` is an earlier cheap-scorer
run (recall@1 0.914, git `e171605`) and is not the cited receipt.

Receipt identity: host `Mac-Studio`, git
`28c2eb6bc5fba57fd4d5a9946c45243a265adcd3`, measured
2026-08-16T22:40:16Z, code `0.1.0`, policy `provisional-1`, scorer
`facebookresearch.dinov2.vits14`.

This session, at SHA `31e6004c76e1d845447e0993a5ce68948f311265`,
ran the same command with no local weights. Scorer
`searcher.cheap_visual.ahash_colour`. Overall: n 35, recall@1
0.914286, recall@5 1.0, recall@10 1.0, MRR 0.940476, false Real 0.
Saved as `artifacts/searcher-public-benchmark.noweights.receipt.json`.
The committed receipt at the §39 path was restored afterwards so
the cited DINOv2 figures remain the ones `CLAIMS.md` and
`tests/unit/test_docs_match_capabilities.py` check.

An independent regeneration on 2026-08-17
(`docs/grading/ROUND_2.md`) reproduced the DINOv2 headline figures
if and only if local weights loaded.

## Retrieval (held-out)

Closed-set: five KIND listings, gallery image 1 versus query image
2, seven degradations. n = 35.

| set | n | recall@1 | recall@5 | recall@10 | MRR |
|---|---:|---:|---:|---:|---:|
| overall | 35 | 0.771429 | 1.0 | 1.0 | 0.866667 |
| blur | 5 | 0.8 | 1.0 | 1.0 | 0.9 |
| crop | 5 | 0.6 | 1.0 | 1.0 | 0.75 |
| heavy_blur | 5 | 0.8 | 1.0 | 1.0 | 0.85 |
| phone_snapshot | 5 | 1.0 | 1.0 | 1.0 | 1.0 |
| pristine | 5 | 0.8 | 1.0 | 1.0 | 0.9 |
| recompressed | 5 | 0.8 | 1.0 | 1.0 | 0.9 |
| small | 5 | 0.6 | 1.0 | 1.0 | 0.766667 |

Quoted as recall@1 0.771, recall@5 1.0, MRR 0.867, matching
`CLAIMS.md` and `tests/unit/test_docs_match_capabilities.py`.

## Bucket decisions (held-out)

Constructed labels on seven synthetic cases. Not authenticity
accuracy.

| label | precision | recall |
|---|---:|---:|
| real | 1.0 | 1.0 |
| possibly_real | 1.0 | 1.0 |
| replica | 1.0 | 1.0 |
| hidden | 1.0 | 1.0 |

False Real: 0 / 7 (0 / 6 labelled-not-Real).

## Shipped pair threshold

`artifacts/searcher-threshold.receipt.json`, same scorer, command
`uv run python -m benchmark.threshold`.

- shipped value 0.86
- held-out TPR 0.5, FPR 0.7 (admits 70% of different-listing pairs)
- verdict: chosen threshold does not hold on held-out data
- calibration-chosen point at 5% FPR ceiling: 0.95 (TPR 0.3, FPR 0.0)

0.86 is a shortlist cut, not an identity gate. The phrase is in
`src/searcher/core/embedding_gateway.py`. The measurement is the
threshold receipt.

On the older, non-reproducible pair calibration
(`artifacts/searcher-match-calibration.receipt.json`): genuine
same-listing pairs have median 0.8101; at threshold 0.90, TPR
0.237 and FPR 0.002. The Real gate needs `item_match >= 0.90`
(`src/searcher/ranking/policy_versions.py`, policy `matching-1`).

## Flagship

`artifacts/searcher-flagship-matched.receipt.json`: 20 of 24
behaviours met, 1 not met, 3 not evaluable. The one not met is
behaviour 15 (Real=0). Input was a Willy Chavarria garment, not
the Bible §40 Dior trainer. Independent re-evaluation in
`docs/grading/ROUND_2.md` reproduced 20 / 1 / 3.

## Live adversarial recall

`artifacts/searcher-adversarial-recall.receipt.json`: 0 / 21 on
three KIND URLs that are not in the cached fixture pack. Treated
as a discovery-coverage finding, not a ranking target.

## What is not established

- Hidden evaluation.
- Live open-set retrieval metrics.
- Authenticity accuracy.
- Conventional-search comparison (Bible §31.8).
- Combined Real + Possibly Real displayed recall as a named live
  metric. The 7-case fixture protocol is not that metric.
- Real-tab precision on live campaigns: live Real count is 0, so
  the denominator is empty.
- A DINOv2 regeneration in this session. No local weights were
  present. The no-weights run is
  `artifacts/searcher-public-benchmark.noweights.receipt.json`.
