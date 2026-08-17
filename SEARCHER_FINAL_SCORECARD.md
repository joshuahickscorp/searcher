# Searcher scorecard

Bible §38 dimensions. Four independent passes, none of them
self-assessed by the code being graded. Columns are labelled by the
commit that was graded, because the round numbering in this project
drifted: the third pass wrote its own scores under a `round_2` key
in `artifacts/grading-round3/scores.json`, and an earlier version of
this table then labelled that column round 2. The commits below are
the unambiguous identifiers.

| Pass | Commit | Where it lives |
|---|---|---|
| 1 | `6c4c5e3` | `artifacts/grading-round3/scores.json`, `round_1` |
| 2 | `a7a5a98` | `docs/grading/ROUND_2.md` |
| 3 | `6435d24` | `artifacts/grading-round3/scores.json`, `round_2` |
| 4 | `4610edd` | `docs/grading/ROUND_4.md`, `artifacts/grading-round4/` |

This file is a Bible §39 document.

Terminal status under §39: **NOT_READY**.

## Grades

| Dimension | `6c4c5e3` | `a7a5a98` | `6435d24` | `4610edd` | Floor |
|---|---:|---:|---:|---:|---:|
| Plan fidelity | 58 | 70 | 78 | 82 | 90 |
| Implementation completeness | 62 | 73 | 80 | 84 | 90 |
| Real-runtime proof | 45 | 71 | 77 | 76 | 90 |
| User-visible proof | 64 | 73 | 84 | 87 | 90 |
| Retrieval quality | 38 | 64 | 73 | 72 | — |
| Authenticity safety | 42 | 83 | 88 | 89 | 90 |
| Security and privacy | 82 | 83 | 83 | 82 | 90 |
| Cost efficiency | 78 | 80 | 81 | 83 | — |
| Test quality | 60 | 76 | 85 | 83 | 90 |
| Documentation | 55 | 77 | 80 | 80 | — |

Two dimensions fell in round 4. Real-runtime proof lost a point
because the speed receipt did not reproduce, and test quality lost
two because the round found a behaviour the suite did not cover.
Neither is a regression in the product; both are the grade catching
up with what was actually true.

The floor for a critical category is 90. Across four rounds
nothing has reached it. The closest is authenticity safety at 89.

Per-dimension justifications are in `docs/grading/ROUND_2.md` and
`docs/grading/ROUND_4.md`. Machine-readable scores for the first
three passes are in `artifacts/grading-round3/scores.json`.

## What later commits changed, as measurements

These are recorded in commit messages and tests. They are not a
new grade.

| Defect | Evidence |
|---|---|
| Replica reaching Real through 13 + 30 listed phrases | `tests/unit/test_replica_phrases.py`; Round 2 Attack A: reached Real `[]` |
| Unequal label-region hashes treated as a counterfeit product code | commit `f6ecd58`, `tests/unit/test_label_hash_is_not_a_code.py` |
| A garment asked for its sole | commits `e835379`, `f18dda0`, `3fe276b` |
| Correspondence ran on a fallback that cannot tell two objects apart | `src/searcher/matching/correspondence.py`; ORB TPR 1.000 / FPR 0.000 on `fixtures/user_snapshots` |
| Live sources typed by hand, omitting Rebag and naming eBay | commit `31e6004`, `uncredentialed_source_names()` |
| Campaign wall time median 199474 ms → 95705 ms over three runs | `artifacts/searcher-speed.receipt.json` |

## What is still true and unflattering

- **Nothing reaches Real.** Behaviour 15 of §40 fails.
- **The pair threshold does not separate.** 0.86 admits 70% of
  different-listing pairs
  (`artifacts/searcher-threshold.receipt.json`).
- **Three marketplaces cannot be admitted** without defeating a
  challenge or ignoring a robots rule. Two serve no robots file.
- **The backbone comparison that chose DINOv2 is not
  reproducible** from this repository.
- **Residual replica slang** still reached Possibly Real at
  `6435d24`.
- **`31e6004` was never graded on its own.** The next pass ran
  against `4610edd`, so that commit's changes were graded only in
  aggregate with everything after them.

## Regenerating the evidence

```bash
uv run python -m benchmark --all
uv run python -m benchmark.threshold
./scripts/flagship_acceptance.py --help
./scripts/test_all.sh
./scripts/scrub_public_tree.sh
```
