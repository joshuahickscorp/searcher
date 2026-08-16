# Searcher benchmark method

This is the protocol behind `uv run python -m benchmark.run --all`.
It implements Bible §31 as far as authorized data allows. It measures.
It does not retune a threshold and it does not entitle a public accuracy claim.

The numbers live in `artifacts/searcher-public-benchmark.receipt.json`.
The pictures live in `artifacts/benchmark/evidence-board.html`.
The split authority lives in `fixtures/benchmark/splits.json`.

## Command

```bash
uv run python -m benchmark.run --all
```

Same command as `./scripts/run_benchmark.sh`. One process writes every artifact.

## Dataset authority

Only images the project is already permitted to hold:

| Family | Where | Permission |
|---|---|---|
| KIND listings | `fixtures/known_item_kind` | Cached public product photographs from `shop.kind.co.jp`. KIND is admitted by `SOURCE_POLICY` for GET product/collection. Fetch date is in `pack.json`. The Images column for KIND is `no`, so this run does not fetch new KIND photographs. Not operator photographs. |
| Hard-negative cases | `searcher.matching.synth` + `fixtures/hard_negatives` | Project-generated synthetic shoe diagrams. Not marketplace images. Not operator photographs. Labels are constructed from the recipe, not a professional authenticity judgment. |

No new marketplace is scraped. No operator photograph is included.
`fixtures/images/trainer_*.png` are unused: they have no listing identity.

## Splits

One canonical rule, asserted in code and frozen in `fixtures/benchmark/splits.json`.

- Split by **product identity** (KIND handle or constructed-case id).
- An identifier appears in exactly one of `{calibration, held_out}`.
- There is **no authorized hidden-evaluation set**. That split is absent, not invented.
- KIND: handle `8001001141404` (the known-item target) is reserved for held-out. Remaining handles sorted lexicographically; first five calibration, rest held-out.
- Hard-negative cases: seven ids reserved for held-out so the reporting split contains Real, Possibly Real, Replica, and hidden. The rest are calibration.

Calibration is used only to draw the score-versus-outcome curve and to show where the already-shipped 0.86 threshold sits. Thresholds are not refit. Held-out is used only to report retrieval and bucket numbers.

`tests/unit/test_benchmark_splits.py` fails if any identifier appears in both splits.

## Retrieval protocol

Closed-set listing retrieval on the KIND fixtures of the split under test.

- Gallery: local image index 1 of every listing in that split.
- Query: local image index 2 of the target listing, under the seven degradations named in `artifacts/searcher-match-calibration.receipt.json`: pristine, blur, heavy_blur, crop, small, recompressed, phone_snapshot.
- A hit is the correct listing identity at rank k.
- Ranker: DINOv2 ViT-S/14 cosine when local weights load; otherwise Searcher's cheap visual signals (average hash + colour histogram). The receipt names the scorer.
- Metrics: recall@1, recall@5, recall@10, mean reciprocal rank; overall and per degradation.
- Recall@20 is not computed: the authorized gallery is smaller than 20.

The earlier live campaign in `artifacts/searcher-adversarial-recall.receipt.json` is a different protocol (open-set discovery). It published zero results. This benchmark does not treat that zero as a ranking target.

## Bucket protocol

`searcher.ranking.pipeline.judge_candidates` on the constructed hard-negative cases of the split, then `published_public_bucket` so a self-declared replica is scored as Replica.

Labels come from the fixture recipe:

| Case | Constructed label |
|---|---|
| true_match, stock_mixed, mirrored_image, prompt_injection | real |
| different_season, authentic_poor_photos | possibly_real |
| replica_copied_title | replica |
| adjacent_model, different_colourway, counterfeit_excellent_photos, stolen_photos, two_items, copied_product_code, rehosted_sold, ai_generated | hidden |

Metrics: precision and recall per label, confusion matrix, and a separate false-Real count. A false Real is a case whose constructed label is not Real that the engine published as Real.

This is not an authenticity-accuracy claim.

## Calibration

Pair curve on **calibration** KIND listings only.

- Positive: two different authorized photographs of the same listing.
- Negative: gallery photograph of listing A versus gallery photograph of listing B.
- Histogram bins of width 0.1, with counts.
- The shipped threshold 0.86 is taken from `artifacts/searcher-match-calibration.receipt.json` and is **not** refit. The receipt says which bin it sits in, and whether 0.86 is a meaningful point on the score scale actually used.

## Operational metrics

Reported in the same receipt as the quality numbers.

- Wall time per campaign
- Fetches per campaign (0 on this offline run)
- Cache hit rate (1.0: every image came from the authorized fixture cache)
- Images per second

A live campaign's fetch cost is a different protocol; see `artifacts/searcher-performance.receipt.json`.

## Evidence board

`artifacts/benchmark/evidence-board.html` is a single file. Images are JPEG data URIs. There are no external requests. An outsider can read the protocol, the splits, the false-Real callout, the retrieval rows, the bucket rows, and the calibration histogram without knowing the codebase.

## What this benchmark does not cover

- Hidden evaluation
- Live open-set marketplace retrieval
- Authenticity accuracy / professional authentication
- Conventional-search comparison (Bible §31.8)
- Operator photographs, and any image not already in `fixtures/`
- New KIND (or other marketplace) image fetches
- Recall@20, NDCG, colourway accuracy, multilingual retrieval
- Any claim that Searcher is better than another engine

If a metric cannot be computed because the data is not authorized, the receipt names it under `not_computed` rather than omitting it.
