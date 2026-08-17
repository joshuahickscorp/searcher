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

**Nothing this project publishes reaches Real.** Policy
`matching-1` requires item-match lower bound ≥ 0.90, authenticity
lower bound ≥ 0.80, evidence completeness ≥ 0.65, a calibrated
authenticity interval, and a live destination-verified listing
(`SEARCHER_BUCKET_POLICY.md`,
`src/searcher/ranking/policy_versions.py`). On
`artifacts/searcher-match-calibration.receipt.json` the scorer's
median on genuine same-listing pairs is 0.8101 and TPR at 0.90 is
0.237. Live campaigns in this tree publish to Possibly Real. KIND
destination verification has been observed to answer with a
challenge (`tests/unit/test_verification.py`).

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

**Calibration is not field-calibrated.**
`fixtures/calibration/footwear_v1.json` records
`not_field_calibrated: true`. Uncalibrated authenticity cannot
pass the Real gate under `matching-1`.

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

- A field reliability curve for authenticity.
- That every residual replica phrasing is now caught. No
  independent regrade has been run at SHA `31e6004`.
