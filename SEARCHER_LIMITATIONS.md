# Searcher limitations

Bible §39 name. Draws from `LIMITATIONS.md` and `CLAIMS.md`.
This file is the negative half of the public claim ceiling. The
positive half is `CLAIMS.md`, restated in
`SEARCHER_TERMINAL_REPORT.md`.

## Prohibited claims (Bible §2.2)

Searcher does not claim:

- guaranteed authenticity;
- professional authentication;
- counterfeit detection with universal accuracy;
- exhaustive coverage of the internet;
- access to every marketplace;
- guaranteed purchase availability;
- guaranteed seller trustworthiness;
- guaranteed lowest price;
- universal brand, category, or era coverage;
- superiority over conventional image search without a frozen
  comparison;
- that a blocked source contained no result;
- that a result is authentic solely because a marketplace says it
  is authenticated;
- that a result is fake solely because the model is uncertain.

Searcher does not place orders, enter payment information,
negotiate with sellers, automate bids, bypass access controls,
impersonate the user, or publish accusations against sellers.

## Limitations that are true of this tree

**Real is scoped to designer footwear.** That is a design
decision, not a matcher failure. The product refuses to put a
listing in Real when it has no calibration table for that
listing's authenticity profile. It can produce Real inside the
one profile it does calibrate.

Exactly one table ships. Confirm the tree, then the profile the
locator loads and the profile it rejects:

```bash
git ls-tree -r --name-only HEAD fixtures/calibration
uv run python -c "from searcher.authenticity.calibration import locate_default_table, load_table, table_applies; t=load_table(locate_default_table()); print(t.profile, table_applies(t,'handbag'), t.method, t.provenance)"
```

Output: `fixtures/calibration/footwear_v1.json`, then
`designer_footwear False`, method
`piecewise-bin reliability on synthetic holdout`, provenance
`n=24`, `fitted_on=fixtures/hard_negatives`,
`not_field_calibrated=True`. `locate_default_table` is hardcoded
to that filename (`src/searcher/authenticity/calibration.py:52`).
`table_applies` (`src/searcher/authenticity/calibration.py:59-63`)
is `table.profile == profile_id`. The engine drops the table when
that is false (`src/searcher/authenticity/engine.py:133-135`).
`profile_for("footwear")` resolves to `designer_footwear`
(`src/searcher/authenticity/profiles/footwear.py:8`,
`src/searcher/authenticity/profiles/__init__.py:9-14`). A
handbag is `generic:handbag`
(`src/searcher/authenticity/profiles/base.py:30-32`).

Everything else takes the uncalibrated interval from
`apply_calibration` (`src/searcher/authenticity/calibration.py:69-71`),
whose spread is 0.22. A raw mean of 1.0 still yields lower bound
0.78 against a Real authenticity gate of 0.80. `matching-1` then
refuses any uncalibrated interval, independently of that number:

```bash
uv run python -c "from searcher.authenticity.calibration import apply_calibration; iv,cal,tag=apply_calibration(1.0, None); print(iv.lower_bound, cal, tag)"
uv run python -c "from searcher.ranking.policy_versions import load_policy; p=load_policy('matching-1'); print(p.require_calibrated_for_real, p.real.authenticity_lower_bound, p.real.authenticity_lower_bound-0.01)"
```

Output: `0.78 False uncalibrated` and `True 0.8 0.79`.
`make_interval` subtracts the spread
(`src/searcher/matching/scores.py:13-16`). `matching-1` sets
`require_calibrated_for_real=True`
(`src/searcher/ranking/policy_versions.py:37`) and
`authenticity_lower_bound=0.80`
(`src/searcher/ranking/policy_versions.py:29`). `combine_authenticity` writes that tag onto
`authority_ceiling` (`src/searcher/authenticity/decision.py:62,90`).
`route_candidate` then clamps an uncalibrated
candidate to the gate minus 0.01
(`src/searcher/ranking/buckets.py:42-46`). Combined, an
uncalibrated listing cannot satisfy Real.

The table is not a market reliability curve and footwear Real is
not field-validated. Its own provenance records
`not_field_calibrated: true`, `n: 24`,
`fitted_on: "fixtures/hard_negatives"`, method
`piecewise-bin reliability on synthetic holdout`, notes
`Identity-preserving bins from the synthetic corpus. Not a
market reliability curve.`
(`fixtures/calibration/footwear_v1.json:4-10`). A Real label on
designer footwear rests on that synthetic fixture. The unit test
that publishes Real is
`tests/unit/test_real_gate_inputs.py:340-368`
(`test_footwear_true_match_can_still_be_real`):

```bash
uv run pytest tests/unit/test_real_gate_inputs.py::test_footwear_true_match_can_still_be_real -q
```

**The item-match quality bar is a separate limit.** Policy
`matching-1` also requires item-match lower bound ≥ 0.90 and
evidence completeness ≥ 0.65
(`src/searcher/ranking/policy_versions.py:28-30`,
`SEARCHER_BUCKET_POLICY.md`). On
`artifacts/searcher-match-calibration.receipt.json` the scorer's
median on genuine same-listing pairs is 0.8101 and TPR at 0.90
is 0.237:

```bash
git show HEAD:artifacts/searcher-match-calibration.receipt.json | python3 -c 'import json,sys; p=json.load(sys.stdin)["pair_calibration"]; print(p["positive_median"], p["sweep_tpr_fpr"]["0.9"])'
```

Output: `0.8101 [0.237, 0.002]`. That bar can keep a calibrated
footwear candidate out of Real. It is not the mechanism that
refuses a garment or a bag. Live campaigns in this tree publish
to Possibly Real. KIND destination verification has been
observed to answer with a challenge
(`tests/unit/test_verification.py`).

**The pair threshold does not separate.** Shipped 0.86 admits 70%
of different-listing pairs on held-out data
(`artifacts/searcher-threshold.receipt.json`). It is a shortlist
cut, not an identity gate.

**The public benchmark is the receipt, not a field study.**
recall@1 0.771, recall@5 1.0, MRR 0.867 over 35 queries, false
Real 0, under DINOv2, command
`uv run python -m benchmark.run --all`. Without local weights the
same command reports a different scorer and different recall@1.

**Learned backbone is optional and local.** A search never
downloads weights. Absent or unreadable weights report
unavailable.

**Correspondence without OpenCV is noise.** On
`fixtures/user_snapshots`, ORB separates at TPR 1.000 and FPR
0.000 at a threshold of 10 inliers; the BRIEF fallback's same-
object and other-object inlier counts overlap
(`src/searcher/matching/correspondence.py`). Install:
`uv sync --extra correspondence`.

**Source coverage is the admitted set only.** Grailed, Vestiaire,
and Taobao cannot be admitted without defeating a challenge or
ignoring robots. Weidian and Yupoo serve no robots file. All stay
disabled. International and review-required adapters ship
disabled.

**No hosted API, no authentication.** The GitHub Pages UI is
static files. `--lan` and `--tunnel` are opt-in and public to
whoever has the URL. Sleep, quit, or a network drop takes the
process down.

**A finished search can honestly return nothing.** Empty Real and
Possibly Real lists are allowed.

**Four code paths assumed footwear.** A garment was asked for its
sole (gap advisor, authenticity profile, compare ontology,
reference view classifier). Commits `e835379`, `3fe276b`,
`f18dda0` changed those paths. Residual footwear parts on a live
garment compare were still recorded at the Round 2 SHA.

**Unequal perceptual hashes of a label region are not a product
code contradiction.** Commit `f6ecd58`. A hash may corroborate
sameness when it matches. Differing is what two honest photographs
do.

**The DINOv2 vs ResNet50 bake-off is not reproducible** from this
repository (`artifacts/searcher-match-calibration.receipt.json`
`reproducibility.status`).

**Residual replica slang** (`not legit`, `god batch`, homoglyph
`repliсa`, `dup`) still reached Possibly Real at the Round 2 SHA
(`docs/grading/ROUND_2.md`). Committed phrase lists (13 + 30) do
not include those.

## What is not established

- A field reliability curve for authenticity. The shipped table
  says it is not one (`fixtures/calibration/footwear_v1.json:9-10`).
- That a Real label on designer footwear would survive a market
  holdout. The only Real path rests on 24 synthetic fixtures.
- That every residual replica phrasing is now caught. No
  independent regrade has been run at SHA `31e6004`.
