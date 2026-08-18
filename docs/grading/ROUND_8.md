I'll grade Searcher at `131696d` independently against Bible §38: first I'll load the contract text, inspect what's actually on disk, and only then run commands that would fail if each claim were false.HEAD is `f8e2ef7` (artifact-dir only); I’ll grade the code at `131696d`. Next I’ll pull Bible §38/§39, the grading-doc shape, and confirm whether `src/` is actually on disk.`src/` isn’t in the sparse tree, so I’ll extract `131696d` to a throwaway archive (not widen sparse-checkout) and pull Bible §38/§39 plus the original four attacks from there.Archive matches `131696d`. Next I’ll pull the §38/§39 contract text and wire the archive so pytest and the benchmark actually import that commit.Main repo venv exists at `<home>/Downloads/searcher`. I’ll pin `PYTHONPATH` to the `131696d` archive, start the long verification runs, and extract the five claimed-change sites plus the original four attacks.The archive imports cleanly. Next I’ll start the long verification runs and pull the five claimed-change implementations plus Wave 13/14 gates.Pytest is running on the archive. I’ll read the five claimed-change sites and write probes that fail if each claim is false.I have the production path: the orchestrator never screens photos or sets `photo_screening_ran`. I’ll write independent probes and start the remaining measurements in parallel.Round 7’s assumptions are stale: the bench now passes `stock_mixed`, and the split guard requires both sides. I’ll measure this commit as it is, not as that report described it.Writing the independent measurement script and launching the remaining verification runs.Measure and benchmark finished. I’ll pull the split and bench numbers, re-check residual replica strings in isolation, and start a live campaign.The first bench run looks like the cheap scorer (recall@1 0.914), not DINOv2. I’ll confirm the weight identity, rerun with the DINOv2 file, and start the live campaign.Live campaign finished PARTIAL with Real empty and the known-item listing unpublished. I’ll extract the pytest failure summary and inspect the live results in more detail.The Pages copy still says bench screening is absent; this commit’s bench passes stolen/stock oracles, so that sentence is false. I’ll write the scorecard from the measurements.**PARTIAL_WITH_BLOCKERS** at `131696d`. No critical §38.2 dimension is ≥ 90. A live campaign published two openable Possibly Real cards and zero Real. Photographs of KIND listing `8001001141404` never entered the frontier.

Wrote `docs/grading/ROUND_8.md` and `artifacts/grading-round8/scores.json`. Did not edit `src/`, `tests/`, `benchmark/`, or `SEARCHER_*.md`. Prior-round numbers were not used. The sparse worktree has no `src/`, so measurement ran from `git archive 131696d` at `/tmp/searcher-r8-grade`.

## §38 scores

| Dimension | Score | One-line fact | Command |
|---|---:|---|---|
| Plan fidelity | **84** | 24 sources named; `source_limit=9`; known-item miss; §40.15 Real=0; `PARSER_FAILED` never assigned | `measure.py` + live `368d5933` |
| Implementation completeness | **85** | Reserve binds; pairing holds on enrich; orchestrator never screens; vision worker has no `src/` caller | `measure.py` |
| Real-runtime proof | **81** | Live PARTIAL in 52.3s; pytest 14 fail / 26 err / 1232 pass; soak/abuse `-11` | `pytest -q --tb=line` |
| User-visible proof | **85** | Pages `200 12876`; Real=[]; 2 https cards (both 200); `reason_codes` null; DELETE 204→404 | `curl` Pages + results |
| Retrieval quality | **70** | DINOv2 recall@1 **0.771429**; live rank of `8001001141404` absent; target not on 91 frontier rows | `benchmark --all` + DINOv2 weights |
| Authenticity safety | **86** | Unscreened cannot be Real; named replica family closed; `dhgate` / `LJR` / `lookalike` still Real | `measure.py` Attack A |
| Security and privacy | **84** | Scrub working-tree PASS; targeted security green; abuse/soak never started | `pytest tests/security` + scrub |
| Cost efficiency | **82** | Wall 52.3s; used `pages=40/40`; API `pages_fetched=60`, charged field null; 1 of 9 sources searched | live budget + `exploration_page_allowance(40,9)` |
| Test quality | **85** | 12/12 sabotages KILLED; pixel-leakage 5 passed with both sides populated; floor suite not green | mutation + pixel-leakage + `pytest -q` |
| Documentation | **83** | 17 §39 names exist; terminal report bound to `31e6004`; Pages misstates the bench screening protocol | `ls` + Pages HTML |

## REFUTED (prominent)

- **IMAGE_THEFT is still unreachable in production.** Fail-closed holds as `route_candidate`. The orchestrator never passes `photo_screening_ran` or `stolen_photo`, and nothing under `src/` calls `run_vision_worker`. Stolen listings stay off Real because the gate is shut, not because theft was detected.
- **`PARSER_FAILED` is never assigned.** COMPLETE→PARTIAL holds for outcomes the engine actually writes. HTTP 200 with an unparseable body is `SEARCHED_MATCHES_FOUND`. Saturation still returns COMPLETE with `NETWORK_FAILED`.
- **Known-item is not repaired.** `_bytes_present` holds as a function. Live miss is earlier: `8001001141404` was not among 91 frontier URLs.
- **Pages still says bench `false Real 0` was measured with screening absent.** At this SHA the bench passes stolen/stock **oracles**, so `photo_screening_ran` is True. Held-out Real recall is 1.0; `stolen_photos` is Hidden via `IMAGE_THEFT_OR_SCAM`. That is an upper bound, not production.
- **Replica class is not closed.** Named family plus `re–plica` / `inauthentic` / `re/plica` / `r3pl!ca` now veto. `dhgate`, `weidian`, `LJR`, `lookalike`, `yupoo`, `godtier`, `factory pair` still publish Real.

## Claimed changes (measured)

1. Real fail-closed when screening never ran — **HOLD** as a function. **REFUTED** as production theft detection.
2. Digest-grouped splits, 22 no longer on both sides — **HOLD**. Overlap 0. Constructed calibration has 2 cases, held_out 22. One 21-member render group is wholly held_out.
3. COMPLETE requires no unresolved planned source — **HOLD** for written outcomes (live was PARTIAL). **REFUTED** for parse failure.
4. Per-source exploration allowance — **HOLD** as a 2-page reserve when 40/9. First source still takes 24.
5. `match_candidate` picks a matched view pair — **HOLD** on enrich. `_png_for` still prefers the dict key if it diverges from `image_id`.

## Four invariant attacks

- **A:** named family closed; class still open on marketplace slang.
- **B:** COMPLETE with no fetch is BLOCKED.
- **C:** no `DENSE_FEATURES` lie; `LOCAL_CORRESPONDENCE` is Searcher’s ORB; `NEXT_VIEW` is a real missing-view heuristic.
- **D:** router hides empty reason / `javascript:` / empty URL; live cards still have `reason_codes: null`.

## Why PARTIAL_WITH_BLOCKERS

§39 names four tokens and does not define a mapping. Wave 13’s gate is met for upload, stream, openable https links, compare text, and delete. It is not met for Real. A campaign produced live listing links, so NOT_READY would invent a rule the contract does not contain. Blockers this status does not hide: live Real empty, known-item miss, production screening never runs, `PARSER_FAILED` unused, floor suite not green.
