I'll grade Searcher independently at this commit: first the Bible scoring contract and current tree, then measurements that would fail if each claim were false.HEAD is `67c5aaf`, not the requested `6a57689`. I'll locate that commit and pull the Bible scoring contract next.I'll load Bible §38/§39 and the prior report format, then measure the tree at `6a57689` without treating later commits as the grade target.src/ is not on disk, so I’ll archive `6a57689` the same way round 6 did, then pull §38/§39 and the invariant-attack list from the Bible.I'll extract Bible scoring rules, archive commit `6a57689` for measurement, and pull the original four invariant attacks.Extracting `6a57689` into a throwaway tree and reading the five claimed-change sites plus the original four attacks.Archive is importable. Next I’ll start the long verification runs and read the five claimed-change implementations.The parent venv still imports main’s `searcher`. I’ll pin `PYTHONPATH` to the archive and confirm fixtures are actually in that tree.Pixel-leakage tests passed. I’ll keep measuring the five claims and the four invariant attacks while the full suite runs.Pytest is already failing. I’ll pull the Real-gate fixtures and write behavioral probes that would fail if the five claims were false.`PARSER_FAILED` is never assigned in production. I’ll encode that and the other behavioural checks in a script that fails if each claim is false.The long suite is still running. I’ll read the measurements that already finished and reproduce the Real-gate collapse on the benchmark path.The full suite finished. I’ll extract the failure summary, then run the benchmark and a live campaign.I have the measurements. Next I’ll write the round-7 scorecard and `scores.json` from those commands, not from earlier rounds.**PARTIAL_WITH_BLOCKERS.** Graded commit `6a57689` (archive at `/tmp/searcher-r7-grade`), not worktree HEAD `67c5aaf`. No critical §38.2 dimension is ≥ 90. A live campaign on this host published five Possibly Real KIND cards and zero Real. Photographs of KIND listing `8001001141404` still do not return that listing.

Wrote `docs/grading/ROUND_7.md` and `artifacts/grading-round7/scores.json`. Did not edit `src/`, `tests/`, `benchmark/`, or `SEARCHER_*.md`. Prior-round numbers were not used.

## §38 scores

| Dimension | Score | One-line fact | Command |
|---|---:|---|---|
| Plan fidelity | **85** | 24 sources named; `source_limit` derived as 9; known-item miss; §40.15 Real=0; `PARSER_FAILED` never assigned | `python /tmp/searcher-r7-evidence/measure.py` + live `36f22b4e` |
| Implementation completeness | **86** | Both engines bind `ExplorationReserve`; pairing holds on enrich; orchestrator never sets `photo_screening_ran`; vision worker has no `src/` caller | same measure script |
| Real-runtime proof | **80** | Live `36f22b4e` PARTIAL in 103.2s; floor suite not green; soak/abuse `-11` | `python -m pytest -q --tb=line` |
| User-visible proof | **86** | Pages 200/12876; live Real=[]; 5 https cards (first 200); `reason_codes` null | `curl` Pages + `/v1/searches/36f22b4e/results` |
| Retrieval quality | **72** | DINOv2 recall@1 **0.771429** reproduced; live rank of `8001001141404` absent; bucket Real recall 0.0 | `python -m benchmark --all` with host `embedding.pt` |
| Authenticity safety | **84** | Unscreened calibrated footwear cannot be Real; 4 replica strings still publish Real | measure.py Attack A + Real-gate checks |
| Security and privacy | **85** | Scrub PASS; targeted security green; abuse/soak never started | `pytest tests/security` + `./scripts/scrub_public_tree.sh` |
| Cost efficiency | **83** | Wall 103.2s; reported 60 pages vs `page_limit=40`; 1 of 9 answerable sources searched | live coverage + `exploration_page_allowance(40,9)` |
| Test quality | **84** | 12/12 sabotages KILLED; pixel-leakage 3 passed because hardneg calibration is empty; floor suite 16 fail / 26 err | `pytest tests/mutation -q -s` + `pytest -q` |
| Documentation | **83** | All 17 §39 names exist; terminal report bound to `31e6004`; this SHA’s `web/index.html` still headlines `false Real 0` | `ls` of the 17 names + 7 receipts |

## The five claimed changes

1. **Real fail-closed when screening never ran — HOLD as a function, REFUTED as production behaviour.** `route_candidate(..., photo_screening_ran=False)` turns a 0.91/0.80 footwear candidate into Possibly Real; `True` yields Real. The orchestrator never passes the flag. `benchmark/buckets.py` omits `stock_mixed`, so screening is also “off” on the bench. `true_match` at 0.91/0.80 is predicted Possibly Real. `IMAGE_THEFT_OR_SCAM` still needs a `stolen_photo` flag nobody on the live path sets. The two tests that still expect Real (`test_hard_negative_corpus_bucket_table`, `test_end_to_end_judgment_and_artifacts`) failed.

2. **Splits grouped by digest; 22 no longer on both sides — HOLD for overlap, REFUTED as a two-sided constructed split.** Identifier and digest overlap are 0. All **22/22** hardneg cases are held_out. Render groups are size 1 and **21**. Pixel-leakage tests pass because there is no constructed calibration set left.

3. **COMPLETE requires no unresolved planned source — HOLD for outcomes the engine writes, REFUTED for parse failure.** The six listed unresolved outcomes flip COMPLETE to PARTIAL. `PARSER_FAILED` is in that set and is **never assigned**; HTTP 200 is `SEARCHED_MATCHES_FOUND`. `saturation=True` still returns COMPLETE with `NETWORK_FAILED`.

4. **Per-source exploration allowance — HOLD as a 2-page reserve when 40/9.** First source still takes **24** pages. `exploration_page_allowance(5,9)==0`. Live campaign reported **60** pages against `page_limit=40`.

5. **`match_candidate` picks a matched view pair — HOLD on the enrich path.** `_best_view_pair` chose the blue descriptor with the blue bytes on a trap that would mix primary-desc with first-png. `_png_for` still prefers the dict key if it ever diverges from `image_id`.

## Four invariant attacks

- **A (replica → Real):** named family publishes replica. Reached Real on `re–plica`, `inauthentic`, `re/plica`, `r3pl!ca`.
- **B (COMPLETE with no fetch):** BLOCKED.
- **C (capability lie):** `DENSE_FEATURES` false; `LOCAL_CORRESPONDENCE` true via Searcher’s ORB (not a lie); `NEXT_VIEW` still advertised without a probe.
- **D (publish without reason or link):** router hides empty reason, `javascript:`, and empty URL. Live API cards still have `reason_codes: null`; the code survives only inside `why.tab_reason`.

## Why PARTIAL_WITH_BLOCKERS

§39 names four tokens and does not define a mapping. §38.2 governs wave completion, not the terminal token. Wave 13/14 READY gates are unmet (Real empty, known-item miss, no critical floor at 90). A campaign on this host accepted three photographs and published five openable listing links, so NOT_READY would invent a rule the contract does not contain. Blockers this status does not hide: Real unreachable on live and on the bench, known-item miss, screening never runs, constructed calibration empty, floor suite not green, four replica Real leaks.

---

## STATUS

PARTIAL_WITH_BLOCKERS. No critical §38.2 score is ≥ 90. Live Real is empty. Known-item photographs do not retrieve `8001001141404`.

## CLAIMS

1. Real fail-closed when screening never ran: **HOLD** as `route_candidate`. **REFUTED** as production IMAGE_THEFT reachability.
2. 22 digests no longer in both splits: **HOLD**. Constructed calibration empty: **REFUTED** as a two-sided split.
3. COMPLETE forbids unresolved planned sources: **HOLD** for written outcomes. **REFUTED** for parse failure (`PARSER_FAILED` never assigned).
4. Per-source exploration allowance: **HOLD** as a 2-page reserve. First source still takes 24; live pages 60 vs limit 40.
5. `match_candidate` picks a matched view pair: **HOLD** on enrich/prepare_reference.
6. Named replica family cannot publish Real: **HOLD**. Class closed: **FAIL** (4 leaks).
7. §32.9 twelve sabotages killed: **HOLD**.
8. Campaign names all 24 sources: **HOLD** (`36f22b4e`).
9. DINOv2 recall@1 0.771 reproduces with weights: **HOLD**. `false Real 0` is not authenticity evidence.
10. Known-item retrieve `8001001141404`: **FAIL**.
11. §40 behaviour 15: **FAIL**.

## EVIDENCE

- `python -m pytest -q --tb=line` → 16 failed, 646 passed, 3 skipped, 1 deselected, 26 errors in 549.19s
- `python -m pytest tests/unit/test_pixel_leakage_guard.py -q` → 3 passed
- `python -m pytest tests/mutation -q -s` → 12 passed, 12 KILLED
- `SEARCHER_EMBEDDING_WEIGHTS=… python -m benchmark --all` → recall@1 0.771429, false Real 0, bucket Real recall 0.0
- `python /tmp/searcher-r7-evidence/measure.py` → 32 HOLD / 4 FAIL / 3 NOTE
- live `36f22b4e` PARTIAL 103.2s, Real=[], 5 Possibly Real, 24 named sources, target absent
- Pages `200 12876`; target listing HTTP 200; first published card HTTP 200
- ruff clean; mypy 269 files clean; scrub PASS on the parent git tree

## CHANGES

Wrote `docs/grading/ROUND_7.md` and `artifacts/grading-round7/scores.json` (plus measurement copies under that directory). Did not edit `src/`, `tests/`, `benchmark/`, or `SEARCHER_*.md`.

## TESTS

Targeted 175 passed. Mutation 12/12 killed. Pixel-leakage 3 passed. Isolated spawn units 6 passed. Floor suite 16 failed / 26 errors (two product Real assertions plus SIGSEGV spawn/abuse). Live campaign finished PARTIAL.

## RISKS

Fail-closed Real without a production screener makes empty Real and `false Real 0` tautological. Digest grouping emptied constructed calibration. Live `pages_fetched=60` exceeds `page_limit=40`. Replica class still open on four spellings. Child-process SIGSEGV still kills soak/abuse.

## UNRESOLVED

Live Real=0; known-item miss; four replica Real leaks; screening never runs on the orchestrator path; constructed calibration empty; `PARSER_FAILED` unused; floor suite not green; coverage receipt still `7a3f314`.

## NEXT

Private-alpha READY, as Wave 13 actually defines it, needs the photographed listing retrieved, Real opened only after a screener production runs, and a critical §38.2 dimension at 90 with a green floor suite. The contract does not require that promotion; it requires the blockers above to stay named until then.
