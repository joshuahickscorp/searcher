# Searcher scorecard

Bible §38 dimensions. Round 1 was graded on 2026-08-16 at commit
`6c4c5e3`. Round 2 is the independent pass in
`docs/grading/ROUND_2.md`, graded 2026-08-17 at commit `6435d24`.
Nothing here is self-assessed by the code that was graded.

This file is a Bible §39 document. It replaces the earlier text
that said Round 2 had not been run.

Terminal status under §39: **NOT_READY**.

SHA `31e6004c76e1d845447e0993a5ce68948f311265` has not been
independently regraded. The numbers below stand as the last
adversarial scores.

## Grades

| Dimension | Round 1 | a7a5a98 | Round 2 (`6435d24`) | Floor |
|---|---:|---:|---:|---:|
| Plan fidelity | 58 | 70 | 78 | 90 |
| Implementation completeness | 62 | 73 | 80 | 90 |
| Real-runtime proof | 45 | 71 | 77 | 90 |
| User-visible proof | 64 | 73 | 84 | 90 |
| Retrieval quality | 38 | 64 | 73 | — |
| Authenticity safety | 42 | 83 | 88 | 90 |
| Security and privacy | 82 | 83 | 83 | 90 |
| Cost efficiency | 78 | 80 | 81 | — |
| Test quality | 60 | 76 | 85 | 90 |
| Documentation | 55 | 77 | 80 | — |

The floor for a critical category is 90. In Round 2 nothing
reached it.

Round 2 one-line justifications are in `docs/grading/ROUND_2.md`.
Scores are also stored at `artifacts/grading-round3/scores.json`.

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
- **Round 3 of SHA `31e6004` has not been graded.**

## Regenerating the evidence

```bash
uv run python -m benchmark --all
uv run python -m benchmark.threshold
./scripts/flagship_acceptance.py --help
./scripts/test_all.sh
./scripts/scrub_public_tree.sh
```
