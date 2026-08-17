# Searcher release readiness

Bible §39 name. Readiness is judged against Bible §38.2 floors,
Bible §40 flagship behaviour, and the four terminal statuses in
§39. This is not a launch recommendation.

## Status

**PARTIAL_WITH_BLOCKERS**

This corrects a previous **NOT_READY** that rested on a reading the
contract does not support. Two corrections, both checkable:

**The terminal status is not a function of §40.** §39 defines four
statuses — `PRIVATE_ALPHA_READY`, `PUBLIC_ALPHA_READY`,
`PARTIAL_WITH_BLOCKERS`, `NOT_READY`. Those tokens appear exactly
once in the whole Bible, in that list. No clause anywhere says an
unmet §40 behaviour forces `NOT_READY`, and no clause defines when
each status applies. The status is a declaration the terminal report
must make honestly.

**§38.2 governs wave completion, not the terminal status.** It says a
critical wave is not complete below 90 and must be reopened,
repaired, rerun and regraded. It contains no terminal-status
language. The earlier text used that floor to override
`PARTIAL_WITH_BLOCKERS` after correctly observing that the status
"would describe a working search that returns Possibly Real results,
and that search exists".

`PARTIAL_WITH_BLOCKERS` is the status that matches observed reality:
a working search, with blockers named below and not hidden.

`PRIVATE_ALPHA_READY` and `PUBLIC_ALPHA_READY` remain unavailable
while the §38.2 floors are unmet and source coverage reaches one
source of nine.

### §40 behaviour 15, measured rather than assumed

"High-evidence candidates appear in Real." §40's scenario input is a
Dior Homme General Army Trainer — designer footwear, the one category
that ships a calibration table. On the bucket benchmark, `true_match`
publishes as **Real** with item-match lower bound **0.91** and
authenticity lower bound **0.80**, with **false Real 0** and
precision **1.0** in every lane. High-evidence candidates do appear
in Real for the flagship's own category.

Reproduce: `uv run python -m benchmark --all`, then read
`artifacts/searcher-public-benchmark.receipt.json` → `buckets`.

### What is genuinely blocked

- **Real is out of scope for uncalibrated categories.** An
  uncalibrated interval carries a spread of 0.22, so a raw 1.0 still
  yields 0.78 against a gate of 0.80, and `ranking/buckets.py`
  independently clamps uncalibrated candidates below the gate. Only
  `designer_footwear` ships a table, and that table records
  `not_field_calibrated: true`, `n: 24`, synthetic. Widening Real
  needs field-collected labelled authenticity ground truth.
- **A campaign reaches one source of nine.** The catalogue walk is
  now shared, but non-catalogue frontier fetches still let one source
  spend the campaign page budget.
- **No §38.2 critical floor is met.** Round 6 at `72cc839`: plan
  fidelity 88, implementation completeness 88, real-runtime proof 79,
  user-visible proof 89, authenticity safety 86, security and privacy
  86, test quality 85.

## Critical floors (Bible §38.2)

A critical wave is not complete when any of these are below 90:
plan fidelity, implementation completeness, real-runtime proof,
security/privacy, authenticity safety, test quality. A user-
visible product wave also needs user-visible proof ≥ 90.

Last independent scores, commit `6435d24`:

| Dimension | Score |
|---|---:|
| Plan fidelity | 78 |
| Implementation completeness | 80 |
| Real-runtime proof | 77 |
| User-visible proof | 84 |
| Retrieval quality | 73 |
| Authenticity safety | 88 |
| Security and privacy | 83 |
| Cost efficiency | 81 |
| Test quality | 85 |
| Documentation | 80 |

SHA `31e6004` has not been independently regraded. Commits after
`6435d24` include category-aware views, the label-hash fix,
correspondence honesty, live-campaign overlap, and registry-
derived source planning. Those do not add a calibration table
for any category except designer footwear, and they do not lift
every floor to 90.

## Blockers that keep the status at NOT_READY

1. **§40.15 on the scored campaign is a garment against a
   footwear-only Real scope.** Flagship receipt: 20 met, 1 not
   met (behaviour 15, Real=0), 3 not evaluable. Input was a
   Willy Chavarria garment, not the Bible's Dior trainer.

   ```bash
   git show HEAD:artifacts/searcher-flagship-matched.receipt.json | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["summary"]); print([b for b in d["behaviours"] if str(b.get("n"))=="15"][0]); print(d["counts"]); print(d["input"]["text"])'
   ```

   Output: `{'met': 20, 'not_met': 1, 'not_evaluable': 3, 'of': 24}`;
   verdict `not met`, observation `Real=0`; counts
   `real 0 / possibly_real 3 / hidden 3`; text starts
   `WILLY CHAVARRIA`. The empty Real tab on that receipt is the
   scope limit applying (`SEARCHER_LIMITATIONS.md`). A synthetic
   footwear fixture does publish Real
   (`tests/unit/test_real_gate_inputs.py:340-368`).
2. **The item-match quality bar is unmet.** Gate 0.90 versus
   median genuine pair 0.8101 (TPR 0.237 at 0.90).

   ```bash
   git show HEAD:artifacts/searcher-match-calibration.receipt.json | python3 -c 'import json,sys; p=json.load(sys.stdin)["pair_calibration"]; print(p["positive_median"], p["sweep_tpr_fpr"]["0.9"])'
   uv run python -c "from searcher.ranking.policy_versions import load_policy; print(load_policy('matching-1').real.item_match_lower_bound)"
   ```

   Output: `0.8101 [0.237, 0.002]` and `0.9`. That bar can fail
   a calibrated footwear candidate. It is not the reason a
   garment is refused Real. KIND destination verification has
   answered with a challenge (`tests/unit/test_verification.py`).
3. **Pair threshold FPR 0.70** at the shipped 0.86 cut on
   held-out DINOv2 pairs.
4. **Residual replica slang** still reached Possibly Real at the
   last independent pass.
5. **History scrub is dirty.**
6. **Soak/abuse still force live discovery off.**
7. **Three marketplaces cannot be admitted** without defeating a
   challenge or ignoring robots; two serve no robots file.

## What a private alpha would still be

An operator can run `./scripts/first_run.sh` or
`./scripts/serve_shared.sh` and search admitted sources. The
published page is static. A tunnel is opt-in and unauthenticated.
That is an operator action, not a Bible-ready launch.

## Clean clone

Bible §32.8. Last committed operator clone is
`artifacts/operator/RECEIPT.md` at public SHA `a66414e`, not
`31e6004`. A clean clone was not re-run in this session (local-
only constraint; this environment also forbids a kernel TCP bind).
See `artifacts/searcher-clean-clone.receipt.json`.

## Mutation tests

Bible §32.9. Not established. No mutation-testing receipt is in
this tree.

## What is not established

- That SHA `31e6004` would score above the floors if independently
  regraded.
- A field-calibrated authenticity table for any category,
  including designer footwear. The shipped table records
  `not_field_calibrated: true` and `n: 24` on
  `fixtures/hard_negatives`
  (`fixtures/calibration/footwear_v1.json:6-9`).
- That a live campaign of the Bible's Dior trainer would meet
  §40.15. The product can emit Real for `designer_footwear` on
  the synthetic fixture; that is not a field demonstration.
