# Authenticity floor

The Real gate needs `authenticity_lower_bound >= 0.80`. The most
favourable input this project can construct — the Rebag Celine Boston
Bag listing’s own photographs used as the query, circular by
construction — produces **0.395789**. That number is not a scorer
arithmetic bug. It is the designed uncalibrated interval of a bag
profile that has no calibration table and no construction, label-code,
or provenance measurement. **0.80 is not reachable under the current
evidence model** for any uncalibrated category, including this one.

This is **case 1**: the scorer is doing what it is written to do; the
evidence class that would open the gate is not collected. Name of that
class: **a field-calibrated authenticity reliability table for the
listing’s category**, plus the physical discriminators the engine
cannot currently take on a bag (a product-code / heat-stamp read, a
real logo or hardware model, provenance documents, non-footwear
construction). Two extractor defects sit next to that limit and are
named below. They were not fixed in this lane.

---

## Candidate

Public e2e receipt, query 2 (one listing photograph as the query)
against the live Rebag listing.

```bash
python3 -c "import json; q=json.load(open('artifacts/searcher-public-e2e.receipt.json'))['queries'][1]; print(q['listing_url']); print(q['authenticity_lower_bound']); print(q['item_match_lower_bound'])"
```

```
https://shop.rebag.com/products/handbag-celine-boston-bag-triomphe-coated-canvas-small-144114525
0.395789
0.802387
```

Query 3 (five of the listing’s own views as the query) is the same
listing with a different reference pick:

```bash
python3 -c "import json; q=json.load(open('artifacts/searcher-public-e2e.receipt.json'))['queries'][2]; print(q['authenticity_lower_bound'])"
```

```
0.387116
```

Category is `bag` (`category_of("Bag")` in
`src/searcher/reference/vocab.py`). Profile is `generic:bag`
(`profile_for` in `src/searcher/authenticity/profiles/__init__.py`).
The only shipped calibration table is
`fixtures/calibration/footwear_v1.json` with `"profile":
"designer_footwear"`. `table_applies` (`calibration.py:59-63`)
rejects it for a bag, so the interval is marked `uncalibrated`.

---

## How the lower bound is made

1. Each assessor returns a `ScoreWithEvidence` with a mean and a
   component spread (`scored` / `make_interval` in
   `src/searcher/matching/scores.py`).
2. `combine_authenticity` (`decision.py:25`) keeps only
   **established** terms (`decision.py:94-108`): a term is dropped if
   `fact_class is UNRESOLVED` or any `missing` token starts with
   `unestablished:`. Placeholder means of terms that are merely
   recorded missing (`label-view`, `provenance`,
   `cross-view-second-image`) **stay in the average**.
3. Weighted mean uses `AUTH_WEIGHTS` (`decision.py:13-22`). Weights
   of dropped terms are renormalised away (`weighted_mean`).
4. If there is no hard contradiction and completeness ≥ 0.65, add
   0.12 (`decision.py:56-57`). Price may only pull down
   (`decision.py:59`). A hard contradiction caps the raw mean at 0.22
   (`decision.py:60-61`).
5. No applicable table → `apply_calibration` returns
   `make_interval(raw, spread=0.22)` (`calibration.py:69-71`).
   Component spreads are discarded here. The public lower bound is
   `raw - 0.22`, clamped and rounded to six decimals
   (`matching/scores.py:14-25`).

`matching-1` then refuses any uncalibrated interval at the Real gate
regardless of the number: `require_calibrated_for_real=True`
(`ranking/policy_versions.py:37`) forces the value used for Real to
`min(lower_bound, 0.80 - 0.01) = 0.79` (`ranking/buckets.py:42-46`).

---

## Best-candidate components

One listing photograph as both the query and the only scored
candidate image. That is the input that produces the receipt’s
0.395789 (the live path downloads one image per listing first,
`campaigns/orchestrator.py:618-619`; authenticity only sees images
that have a `content_digest`, `_candidate_pngs` at
`orchestrator.py:721-732`).

Settled by running `assess_authenticity` on
`ABB1934-1.jpg` (the listing’s first CDN photograph) against itself,
category `bag`. Reproduction is in the appendix. The same arithmetic
with no engine import:

```bash
python3 - <<'PY'
W = dict(label=0.16, logo=0.12, material=0.12, photo=0.12,
         originality=0.08, source=0.08, provenance=0.08)
M = dict(label=0.42, logo=0.84, material=0.85, photo=0.55,
         originality=0.70, source=0.55, provenance=0.40)
raw = sum(W[k]*M[k] for k in W) / sum(W.values())
print(raw)
print(round(raw, 6), round(raw - 0.22, 6))
PY
```

```
0.6157894736842104
0.615789 0.395789
```

| Component | Weight | Mean | Spread | In the mean? | Fired or recorded missing |
|---|---:|---:|---:|---|---|
| construction | 0.24 | 0.50 | 0.25 | no | recorded missing: `unestablished:construction`. Generic profile’s only check is `silhouette`, which is not in `MEASURABLE_CONSTRUCTION` (`construction.py:25-37`, `profiles/base.py:40`). |
| label | 0.16 | 0.42 | 0.22 | yes | recorded missing: `label-view` (`labels.py:27-29`). `label_hash` is None. |
| logo | 0.12 | 0.84 | 0.08 | yes | fired. Support `ev:logo:placement` (`logos.py:31`). Same-pixel gold-centroid distance 0. |
| material | 0.12 | 0.85 | 0.12 | yes | fired. Identical `dominant_rgb`, colour distance 0 (`materials.py:21-34`). |
| photo | 0.12 | 0.55 | 0.10 | yes | recorded missing: `cross-view-second-image` (`matching/cross_image.py:15-16`). One descriptor. |
| originality | 0.08 | 0.70 | 0.10 | yes | fired at the assessor’s cap. No `image_records` → `families = 1` → 0.70 (`originality.py:18-19`). There is no higher bin. |
| source | 0.08 | 0.55 | 0.14 | yes | fired at the assessor’s cap (`source_signals.py:27`). Age / payment only pull down. A platform badge cannot raise. |
| provenance | 0.08 | 0.40 | 0.20 | yes | recorded missing: `provenance` (`provenance.py:15-19`). Title + description contain none of `receipt`, `box`, `dust bag`, `dustbag`, `invoice`. |
| price | 0.00 | 0.50 | 0.05 | n/a | fired, anomaly-only. Cannot raise (`engine.py:44-52`, `core/policy.py:apply_price_to_authenticity`). |

Construction’s 0.24 is dropped. Remaining weight is 0.76.
Completeness on one `front` view against
`expected_views = (front, rear, detail, label)`:

```bash
python3 -c "print(round(0.6*(1/4)+0.4*1.0, 4))"
```

```
0.55
```

0.55 < 0.65, so the +0.12 completeness lift does not apply
(`decision.py:56-57`). No hard contradictions, so the raw mean is
not capped. Uncalibrated spread 0.22:

`0.6157894736842104 - 0.22 = 0.3957894736842105` → **0.395789**.

Five-view query, still one candidate image: `_pick` chooses
`ABB1934-5` (largest `subject_area` among the five; all
`keypoints` are 0). Colour distance against `ABB1934-1` is
0.019618 → materials 0.795069. Same command path as the appendix,
five files as reference:

```
established_raw 0.6071161578947368
lower_bound     0.387116
```

That is the receipt’s second authenticity number.

---

## Ceiling when everything that can fire does fire

Assessor success means, from the source:

```bash
python3 - <<'PY'
# construction.py:63  labels.py:49  logos.py:31  materials.py:24
# photo: 1.0 - 0*2.4  originality.py:19  source_signals.py:27
# provenance.py:20
W = dict(construction=0.24,label=0.16,logo=0.12,material=0.12,
         photo=0.12,originality=0.08,source=0.08,provenance=0.08)
mx = dict(construction=0.90,label=0.82,logo=0.84,material=0.85,
          photo=1.00,originality=0.70,source=0.55,provenance=0.62)
print('all_fire_raw', sum(W[k]*mx[k] for k in W))
rest = {k:v for k,v in mx.items() if k!='construction'}
raw_x = sum(W[k]*rest[k] for k in rest)/sum(W[k] for k in rest)
print('no_construction_raw', raw_x)
print('no_construction_plus_completeness', raw_x+0.12)
print('uncalibrated_lb_that', round((raw_x+0.12)-0.22, 6))
print('uncalibrated_lb_at_raw_1', round(1.0-0.22, 6))
PY
```

```
all_fire_raw 0.8196
no_construction_raw 0.7942105263157894
no_construction_plus_completeness 0.9142105263157894
uncalibrated_lb_that 0.694211
uncalibrated_lb_at_raw_1 0.78
```

On a bag, construction cannot fire. The theoretical ceiling on the
**lower bound**, every other assessor at its own maximum, completeness
bonus applied, uncalibrated, is **0.694211**.

Even a fabricated raw mean of 1.0 still yields **0.78**, because the
uncalibrated spread is 0.22 (`calibration.py:71`). 0.78 < 0.80.

Footwear is the exception: `fixtures/calibration/footwear_v1.json`
maps raw ∈ [0.78, 0.90) to mean 0.86 / spread 0.06 → lower bound
**0.80**, and raw ∈ [0.90, 1.01) to 0.93 / 0.05 → **0.88**. The unit
test `test_footwear_true_match_can_still_be_real` passes (overlay
pytest, below). Bags have no such table. Applying the footwear bins
to this listing’s raw 0.615789 would land in [0.45, 0.62) →
calibrated lower bound 0.40. Calibration without a higher raw mean
does not open the gate either.

What this listing can actually collect today, if every downloaded
photograph is scored and the gold-pixel “logo” happens to agree with
itself (the ten-image circular run): established raw 0.652105,
completeness 0.70 so +0.12, uncalibrated lower bound **0.552105**.
Still 0.25 short of 0.80. If the gold-pixel centroids on different
views disagree (`dist >= 0.18` or kind mismatch),
`logo-incompatible` is a hard contradiction (`logos.py:28-30`) and
the interval collapses to mean 0.22 / lower 0.00.

**0.80 is not reachable for this candidate, or for any uncalibrated
profile, under the current evidence model.**

---

## Case, and the missing evidence class

**Case 1.** The combination arithmetic is working. The 0.395789
figure is exactly `make_interval(established_mean, 0.22)` on the
terms the assessors emit for a circular bag photograph. Nothing in
`decision.py` or `calibration.py` is dropping a term it should have
kept, other than construction, which is unpublished on purpose.

Authenticity certification at 0.80 needs evidence this product does
not collect:

1. **A field-calibrated reliability table for the category.** The
   only table is a 24-row synthetic footwear fixture marked
   `not_field_calibrated: true`. Uncalibrated authenticity cannot
   satisfy `matching-1` Real (`SEARCHER_BUCKET_POLICY.md`,
   `policy_versions.py:37`, `buckets.py:42-46`). This is the class
   that actually holds the gate shut even if every other term were
   1.0.
2. **A product-code / heat-stamp read.** The listing includes a
   close-up of the stamped code `MC98/2 MADE IN ITALY`
   (`ABB1934-10.jpg`). The engine never reads it. `_label_hash`
   (`matching/structure.py:266-276`) returns None unless the crop’s
   mean grey is ≥ 170 (a bright paper size card). Measured mean on
   that stamp is 141.3. `assess_labels` then records `label-view`
   missing (`labels.py:27-29`).
3. **A real logo / hardware detector.** `LOGO_DETECTION` is
   advertised unavailable. `_logo` (`matching/structure.py:212-224`)
   is a gold/yellow pixel hunt written for the synthetic shoe
   renderer (`r > 180 and g > 140 and r - b > 60`). It lights up on
   tan leather and coated canvas, invents a `logo_xy`, and on one
   image reports `ev:logo:placement` at 0.84. That is not a Celine
   plaque measurement.
4. **Provenance documents.** Rebag tags this SKU `dust-bag`.
   `assess_provenance` only substring-searches title and
   description (`provenance.py:11-19`) and does not hyphen-fold, so
   `dust-bag` is not `dust bag` or `dustbag`. There is no receipt,
   invoice, or dust-bag photograph path.
5. **Non-footwear construction.** `generic:bag` publishes
   `construction_checks=("silhouette",)` (`profiles/base.py:40`).
   Silhouette is not measurable. The 0.24 construction weight is
   removed from the mean.

Originality cannot exceed 0.70 and source cannot exceed 0.55. Those
caps are intentional “supportive, never decisive” policy
(`SEARCHER_AUTHENTICITY_POLICY.md`). They are part of the evidence
model, not a mis-report.

If labels were repaired to 0.82 on this same one-image input and
nothing else changed:

```bash
python3 -c "print(round((0.16*0.82+0.12*0.84+0.12*0.85+0.12*0.55+0.08*0.7+0.08*0.55+0.08*0.4)/0.76 - 0.22, 6))"
```

```
0.48
```

Still 0.32 short of 0.80. A wrongly-missing label is real; it is not
why the gate is 0.40 away.

---

## Defects found (not fixed)

Reported because the contract asked which case this is, and these
are the lines that mis-describe evidence. They do not move 0.395789
to 0.80.

1. **`_label_hash` refuses the listing’s serial stamp.**
   `src/searcher/matching/structure.py:275-276` (`if mean < 170:
   return None`). Image 10 is the heat stamp. Mean 141.3. Labels
   then records missing at `src/searcher/authenticity/labels.py:27-29`.
   The evidence is in the listing; the extractor is a bright-card
   filter.
2. **`_logo` is not a logo detector.**
   `src/searcher/matching/structure.py:223-224`. On this bag it
   fires on every photograph, including the interior and the stamp.
   On identical pixels it inflates the score (0.84 instead of a
   missing 0.48). On two different views of the same bag it can
   emit `logo-incompatible` at `src/searcher/authenticity/logos.py:28-30`
   and collapse the interval to 0.00. That is a false hard
   contradiction.

Do not treat either as the reason Real is closed. Close the
calibration and evidence-collection gap and these two still need to
be replaced before a bag score is a measurement of marks.

---

## Appendix — reproduction

Sparse checkout does not materialise `src/searcher/contracts` or
`src/searcher/matching`. Extract a throwaway copy of the package
(do not run `git sparse-checkout add`):

```bash
mkdir -p /tmp/auth-floor-src
git archive HEAD src/searcher | tar -x -C /tmp/auth-floor-src

# Listing photographs used above (Shopify CDN, same handle as the receipt).
mkdir -p /tmp/boston-bag
# ABB1934-1.jpg … ABB1934-10.jpg from
# https://cdn.shopify.com/s/files/1/0384/0161/files/ABB1934-N.jpg

PYTHONPATH=/tmp/auth-floor-src/src \
  uv run python -c "from searcher.authenticity.engine import *; print('scorer imports')"
```

One-image circular run (produces 0.395789) is the `assess_authenticity`
path in `src/searcher/authenticity/engine.py` with
`make_hypothesis(category="bag")`, `enrich_candidate(..., category="bag")`,
`prepare_reference` of `ABB1934-1.jpg`, and that same byte string as
the only candidate image. Measured dump:
`artifacts/authenticity-floor-one-image.json`.

Label-crop means that settle the stamp refusal:

```bash
# mean grey of the _label_hash 32×32 sample, image 10 (the stamp)
# measured 141.3; threshold is 170 at matching/structure.py:275
```

---

## STATUS

The authenticity lower bound on the most favourable input is
0.395789 against a Real gate of 0.80. The gap is an evidence-model
limit (no category calibration; no bag construction, label-code, or
provenance measurement), not a broken weighted mean. 0.80 is not
reachable while the interval is uncalibrated.

## CLAIMS

- The public e2e circular bag listing scores authenticity lower
  bound 0.395789 (one query photograph) and 0.387116 (five).
- That 0.395789 is `make_interval(0.6157894736842104, spread=0.22)`.
- Construction is unpublished for `generic:bag` and is not in the
  mean. Labels, photo-set, and provenance are recorded missing and
  still vote with placeholder means 0.42 / 0.55 / 0.40.
- Logo and material fire; originality and source fire at their caps
  0.70 and 0.55.
- Uncalibrated ceiling on the lower bound is 0.78 at raw 1.0, and
  0.694211 at every fireable assessor maximum with construction
  excluded. 0.80 is unreachable without a calibration table.
- Footwear can still reach Real; `test_footwear_true_match_can_still_be_real`
  passed.
- `_label_hash` (structure.py:275) and `_logo` (structure.py:223)
  mis-describe marks on this listing. Not fixed.

## EVIDENCE

- `artifacts/searcher-public-e2e.receipt.json` queries 2 and 3.
- `artifacts/authenticity-floor-one-image.json` (engine run).
- Commands quoted next to every number in this file.
- `src/searcher/authenticity/{decision,calibration,construction,labels,logos,materials,photo_integrity,originality,source_signals,provenance,profiles/base}.py`.
- `git show HEAD:src/searcher/matching/{scores,structure,cross_image}.py`.
- `git show HEAD:src/searcher/ranking/{policy_versions,buckets}.py`.
- `git show HEAD:fixtures/calibration/footwear_v1.json`.
- Live product JSON
  `https://shop.rebag.com/products/handbag-celine-boston-bag-triomphe-coated-canvas-small-144114525.json`
  (tags include `dust-bag`; body is title-only; ten images).

## CHANGES

- `artifacts/authenticity-floor.md` (this file).
- `artifacts/authenticity-floor-one-image.json` (measured dump).
- No edits under `src/` or `tests/`. No threshold moved.

## TESTS

Specified commands, as written, fail because this worktree is a
sparse checkout (`searcher.contracts` and `searcher.campaigns` are
not on disk):

```text
uv run python -c "from searcher.authenticity.engine import *; print('scorer imports')"
  ModuleNotFoundError: No module named 'searcher.contracts'

uv run pytest tests/unit/test_real_gate_inputs.py -q
  ModuleNotFoundError: No module named 'searcher.campaigns'
```

Same commands against `git archive HEAD src/searcher` on
`PYTHONPATH`:

```text
PYTHONPATH=/tmp/auth-floor-src/src uv run python -c "from searcher.authenticity.engine import *; print('scorer imports')"
  scorer imports

PYTHONPATH=/tmp/auth-floor-src/src uv run pytest tests/unit/test_real_gate_inputs.py -q --tb=line
  9 passed, 2 skipped in 0.82s
```

Skipped: OpenCV correspondence extra, and the Kind fixture path
(not materialised). Footwear Real still passes.

## RISKS

- The one-image reconstruction matches both receipt authenticity
  numbers to six decimals, so it is the live combination. It is
  still a reconstruction: the e2e run did not persist the
  `AuthenticityEvidence` payload, only the lower bound.
- CDN bytes today may not be bitwise-identical to the e2e night.
  The combination is discrete enough that the lower bounds still
  matched.
- Naming `_logo` / `_label_hash` as defects is not a licence to
  retune their constants so a bag can look calibrated.

## UNRESOLVED

- A bag (or generic) calibration table does not exist. Until one is
  fitted on labelled authentic / replica pairs, Real stays closed
  for every non-footwear category by policy, not by 0.01 of raw
  score.
- Whether the live campaign actually stopped at one downloaded
  image for this listing, or only used one in descriptors for
  another reason, is not in the receipt. The arithmetic does not
  care: one descriptor is what 0.395789 requires for `photo = 0.55`.
- Specified verify commands need
  `src/searcher/{contracts,matching,core,campaigns,evidence,ranking,retrieval,hypotheses,reference}`
  materialised if they must be run without a `PYTHONPATH` overlay.

## NEXT

Do not lower 0.80. Do not mark a bag calibrated by reusing the
footwear fixture. If Real is meant to open on handbags, the work is
to collect the evidence class named above and fit a table on it;
then replace the gold-pixel logo hunt and the bright-card label
hash with measurements that can see a heat stamp and a plaque.
