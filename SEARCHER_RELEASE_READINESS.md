# Searcher release readiness

Bible §39 name. Readiness is judged against Bible §38.2 floors,
Bible §40 flagship behaviour, and the four terminal statuses in
§39. This is not a launch recommendation.

## Status

**NOT_READY**

Justified in `SEARCHER_TERMINAL_REPORT.md`. The last independent
§38 grades (`docs/grading/ROUND_2.md`, commit `6435d24`) are all
below the critical floor of 90. Nothing published reaches Real.
§40 behaviour 15 is not met.

`PRIVATE_ALPHA_READY` and `PUBLIC_ALPHA_READY` are not available
on this evidence. `PARTIAL_WITH_BLOCKERS` would describe a working
search that returns Possibly Real results, and that search exists,
but the Bible's completion bar (Real results, floors ≥ 90,
flagship behaviour 15) is not met. The honest launch status is
therefore **NOT_READY**.

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
derived source planning. Those do not, by themselves, put a
result in Real or lift every floor to 90.

## Blockers that keep the status at NOT_READY

1. **Real is unreachable on current evidence.** Gate 0.90 versus
   median genuine pair 0.8101 (TPR 0.237 at 0.90). Live
   authenticity lower bound on garments has been 0.40 with
   completeness 0.80. KIND destination verification has answered
   with a challenge.
2. **§40 behaviour 15 is not met.** Flagship receipt: 20 met, 1
   not met (Real), 3 not evaluable. The scored campaign was a
   Willy Chavarria garment, not the Bible's Dior trainer.
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
- A date on which a Real result will exist.
