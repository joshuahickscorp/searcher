# Searcher release readiness

Bible §39 name. Readiness is judged against Bible §38.2 floors,
Bible §40 flagship behaviour, and the four terminal statuses in
§39. This is not a launch recommendation.

## Status

**NOT_READY**

Justified in `SEARCHER_TERMINAL_REPORT.md`. The last independent
§38 grades (`docs/grading/ROUND_2.md`, commit `6435d24`) are all
below the critical floor of 90.

§40 behaviour 15 ("high-evidence candidates appear in Real",
Bible §40 item 15) is not met on the scored campaign. That
sentence hides two different facts, and they should not be
collapsed:

- **Scope limit (design).** Real is only in scope for
  `designer_footwear`. See `SEARCHER_LIMITATIONS.md`. The
  flagship receipt's input was a Willy Chavarria garment, so
  the authenticity interval is uncalibrated and `matching-1`
  refuses Real by policy. That is not a claim that the product
  cannot produce Real.
- **Quality bar (unmet).** Even inside the calibrated category,
  item-match lower bound 0.90 sits above the genuine-pair
  median 0.8101 (TPR 0.237 at 0.90). A Real label on footwear
  still rests on 24 synthetic fixtures, not a field curve.

`PRIVATE_ALPHA_READY` and `PUBLIC_ALPHA_READY` are not available
on this evidence. `PARTIAL_WITH_BLOCKERS` would describe a working
search that returns Possibly Real results, and that search exists,
but the Bible's completion bar (floors ≥ 90, flagship behaviour
15 on the named Dior trainer) is not met. The honest launch
status is therefore **NOT_READY**.

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
