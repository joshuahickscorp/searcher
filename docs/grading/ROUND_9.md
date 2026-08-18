I'll grade Searcher at `0feff24` independently against Bible §38. First I'm reading the contract, the sparse tree, and the source at that commit so every score is backed by a command that would fail if the claim were false.HEAD is `1968b13`, one commit past the grade target. I’ll pin evidence to `0feff24`, then pull Bible §38/§39 and the prior grade format.Code at `0feff24` is not on disk. I’ll archive that commit, pull Bible §38/§39, and load the four original invariant attacks.Archive is at `/tmp/searcher-r9-grade`. Next I’ll extract §38/§39 and pin imports so tests run against that tree, not the parent venv.The tree-wide find is too slow. I’ll stop it and pull Wave 13/14, the five claim sites, and a usable Python env instead.Archive matches `0feff24`. I’ll pin `PYTHONPATH` to that tree, start the long verification runs, and extract the five claim sites.Orchestrator now sets `photo_screening_ran=True`. I’ll read that path and the other four claim sites, then start the verification suite.Orchestrator now always passes `photo_screening_ran=True`. I need to check whether screening actually ran, or whether that flag just opens the Real gate.There’s a live API on `:8788`, but I won’t treat it as this commit. I’ll start the archive suite and write independent probes.I’ll write an independent measurement script, then launch pytest, the live campaign, and the claim probes in parallel.Index consult writes decisions without screening, and `_rank` returns if decisions already exist. I’m verifying that path before scoring Real.I have the production path. Next I’ll write the measurement script and start the long verification runs.FastOrchestrator still treats a content digest as proof of possession. I’ll add that check, then start the verification suite.Measure finished: 67 HOLD, 8 FAIL. I’ll poll the live campaign and the 8788 search, then inspect the Attack A leftovers.The independent live campaign already finished PARTIAL (Real=0, 5 Possibly Real). I’ll extract results, check the known-item listing, and keep waiting on pytest.Pytest finished: 14 failed, 1278 passed, 26 errors. I’ll pull the failure list and start the benchmark.I have the measurements. Next I’ll write the independent scorecard and `scores.json` from those commands, not from earlier rounds.**PARTIAL_WITH_BLOCKERS** at `0feff24`. No critical §38.2 dimension is ≥ 90. A live campaign published openable Possibly Real cards and zero Real. Photographs of KIND listing `8001001141404` retrieve that listing only from a warm index, not from a cold shop walk.

Wrote `docs/grading/ROUND_9.md` and `artifacts/grading-round9/scores.json`. Did not edit `src/`, `tests/`, `benchmark/`, or `SEARCHER_*.md`. Prior-round numbers were not used. The sparse worktree has no `src/`, so measurement ran from `git archive 0feff24` at `/tmp/searcher-r9-grade`.

## §38 scores

| Dimension | Score | One-line fact | Command |
|---|---:|---|---|
| Plan fidelity | **83** | 24 sources named; 9 answerable; 1 searched; `PARSER_FAILED` assigned; API still seals COMPLETE before unresolved sources are painted; §40.15 Real=0 | `measure.py` + live `fc7260ee` |
| Implementation completeness | **84** | Orchestrator screens and always passes `photo_screening_ran=True`; consult omits the flag; `FastOrchestrator` skips download on a digest | `measure.py` |
| Real-runtime proof | **81** | Cold live PARTIAL in 109.3s; warm-index API COMPLETE with 8 cards; pytest 14 fail / 26 err / 1278 pass; soak/abuse `-11` | `pytest -q --tb=line` |
| User-visible proof | **86** | Pages `200 12873`; Real=[]; 8 https cards (target rank 1 on the warm API); `reason_codes` null; DELETE 204→404 | `curl` Pages + `/v1/searches/2757e98d` |
| Retrieval quality | **72** | DINOv2 recall@1 **0.771429**; cold rank of `8001001141404` absent (0/24, 0/66 frontier); crop/small recall@1 0.6 | `benchmark --all` + DINOv2 weights |
| Authenticity safety | **82** | Unscreened cannot be Real; named/residual replica strings publish replica; a singleton stolen-photo listing publishes Real; `mirror`/`factory`/`AAA+`/`1:1`/`rep` overflag | `measure.py` Attack A |
| Security and privacy | **84** | Working-tree scrub PASS; history dirty; security 29 passed; abuse/soak never started | `pytest tests/security` + scrub |
| Cost efficiency | **81** | Wall 109.3s; `pages_fetched=52` against `page_limit=40`; first source can take 24; 1 of 9 sources searched | live budget + `exploration_page_allowance(40,9)` |
| Test quality | **84** | 12/12 sabotages KILLED; pixel-leakage 5 passed with both sides populated; floor suite not green | mutation + pixel-leakage + `pytest -q` |
| Documentation | **82** | 24/24 §39 names exist; terminal report bound to `31e6004`; Pages still says bench screening was absent | `ls` + Pages HTML |

## REFUTED

- **Singleton stolen photos still publish as Real.** Fail-closed holds as `route_candidate(..., photo_screening_ran=False)`. Production always passes `True` after an intra-set reuse screen. One listing with a brand-lookbook digest, no second seller, is Real with empty vetoes.
- **COMPLETE is sealed before unresolved sources are recorded.** `published_terminal_status` would flip COMPLETE→PARTIAL for `UNMEASURABLE`. Search `2757e98d` is COMPLETE with nine `UNMEASURABLE` rows painted afterwards by `account_for_every_known_source`.
- **Known-item is not repaired on live discovery.** Cold `fc7260ee`: target absent from 24 candidates and 66 frontier rows. The same photographs against a 2250-entry warm index published it first, as Possibly Real (item 0.907, auth 0.231).
- **Pages still says bench `false Real 0` was measured with screening absent.** This SHA’s bench passes stolen/stock oracles; held-out Real recall is 1.0; `stolen_photos` is Hidden via `IMAGE_THEFT_OR_SCAM`.
- **The “minimum” exploration allowance is 0 when 5 pages are shared by 9 sources.** First source can still take 24 of 40.
- **Replica class is closed by over-matching.** `\bmirror\b`, `from the factory`, `AAA+`, `1:1`, `\breps?\b` flag ordinary English.

## Claimed changes

1. Real fail-closed when screening never ran — **HOLD** as a function. **REFUTED** as production theft detection.
2. Digest-grouped splits, 22 no longer on both sides — **HOLD**. Overlap 0. One 21-member group is wholly held_out.
3. COMPLETE requires no unresolved planned source — **HOLD** for written outcomes. **REFUTED** for the live API and for saturation.
4. Per-source exploration allowance — **HOLD** as a 2-page reserve when 40/9. **REFUTED** as a universal minimum.
5. `match_candidate` picks a matched view pair — **HOLD** on enrich. **REFUTED** when dict key and `image_id` diverge.

`PARSER_FAILED` is now assigned on an unreadable HTTP 200 and is wired through `fetch_modes` / `bounded_discovery`. That part of the COMPLETE rule is no longer a dead branch.

## Four invariant attacks

- **A:** named family and residual obfuscations publish replica, never Real. Class still overflags `mirror` / `factory` / `AAA` / `1:1` / `rep`.
- **B:** COMPLETE with no fetch is BLOCKED.
- **C:** no `DENSE_FEATURES` lie; `LOCAL_CORRESPONDENCE` is under-claimed (ORB still ran on the live rank-1 card); `NEXT_VIEW` is advertised as a heuristic.
- **D:** router hides empty reason / `javascript:` / empty URL; live cards still have `reason_codes: null`.

## Why PARTIAL_WITH_BLOCKERS

§39 names four tokens and does not define a mapping. Wave 13 is met for upload, stream, openable https links, compare text, and delete. It is not met for a populated Real tab. A campaign produced live listing links, so NOT_READY would invent a rule the contract does not contain. PRIVATE_ALPHA_READY would ignore §38.2 (no critical dimension ≥ 90, user-visible proof 86).

---

## STATUS

PARTIAL_WITH_BLOCKERS. No critical §38.2 score is ≥ 90. Live Real is empty. Cold discovery does not retrieve `8001001141404`.

## CLAIMS

1. Real fail-closed when screening never ran: **HOLD** as `route_candidate`. **REFUTED** as production IMAGE_THEFT of a singleton stolen listing.
2. 22 digests no longer in both splits: **HOLD**.
3. COMPLETE forbids unresolved planned sources: **HOLD** for written outcomes. **REFUTED** for the live API.
4. Per-source exploration allowance: **HOLD** as a 2-page reserve. **REFUTED** as a universal minimum.
5. `match_candidate` picks a matched view pair: **HOLD** on enrich.
6. `PARSER_FAILED` assigned on unreadable 200: **HOLD**.
7. Named replica family cannot publish Real: **HOLD**. Class closed without false positives: **FAIL**.
8. §32.9 twelve sabotages killed: **HOLD**.
9. DINOv2 recall@1 0.771 reproduces with weights: **HOLD**. `false Real 0` is not authenticity evidence.
10. Known-item retrieve `8001001141404` from live discovery: **FAIL**. From a warm index: **HOLD** (rank 1, Possibly Real).
11. §40 behaviour 15: **FAIL**.

## EVIDENCE

- `python /tmp/searcher-r9-evidence/measure.py` → 67 HOLD / 8 FAIL / 6 NOTE
- `python -m pytest -q --tb=line` → 14 failed, 1278 passed, 1 skipped, 1 deselected, 26 errors in 549.75s
- `python -m pytest tests/unit/test_pixel_leakage_guard.py -q` → 5 passed
- `python -m pytest tests/mutation -q -s` → 12 passed, 12 KILLED
- `SEARCHER_EMBEDDING_WEIGHTS=… python -m benchmark --all` → recall@1 0.771429, false Real 0, scorer `facebookresearch.dinov2.vits14`
- live `fc7260ee` PARTIAL 109.3s, Real=[], 5 Possibly Real, target absent, pages 52/40
- API `2757e98d` COMPLETE, Real=[], 8 Possibly Real, target rank 1, DELETE 204→404
- Pages `200 12873`; ruff clean; mypy 271 files clean; scrub working-tree PASS

## CHANGES

Wrote `docs/grading/ROUND_9.md` and `artifacts/grading-round9/scores.json` (plus measurement copies under that directory). Did not edit `src/`, `tests/`, `benchmark/`, or `SEARCHER_*.md`.

## TESTS

Targeted security 29 passed. Mutation 12/12 killed. Pixel-leakage 5 passed. Floor suite 14 failed / 26 errors (spawn/abuse SIGSEGV, occupied ports). Live campaign finished PARTIAL. Warm-index API campaign finished COMPLETE.

## RISKS

Fail-closed Real plus an always-true production flag makes “screening ran” a tautology unless two sellers share an image in the same campaign. Bench `false Real 0` is an oracle. Replica overflag will hide legitimate listings. COMPLETE can coexist with UNMEASURABLE. `pages_fetched` exceeds `page_limit`. Child SIGSEGV still kills soak/abuse.

## UNRESOLVED

Live Real=0; cold known-item miss; singleton stolen-photo Real; consult unscreened; FastOrchestrator digest skip; COMPLETE painted after the fact; replica overflag; floor suite not green; terminal report still bound to `31e6004`.

## NEXT

Private-alpha READY, as Wave 13 actually defines it, needs Real opened only after a screener that can fire on a singleton stolen listing, known-item retrieval from the shop rather than from a warm index, a critical §38.2 dimension at 90, and a green floor suite. The contract does not require that promotion; it requires the blockers above to stay named until then.
