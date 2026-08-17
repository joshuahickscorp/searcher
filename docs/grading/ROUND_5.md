# Round 5 independent regrade

Graded 2026-08-17 against Bible §38 / §39 at commit
`4fae9f76c761e6be17553f2dff1c2e70b5858448`. This pass did not write `src/`,
`tests/`, `benchmark/`, `scripts/`, `web/`, `fixtures/`, or `pyproject.toml`.
Commit messages, `SEARCHER_FINAL_SCORECARD.md`, and this contract were treated
as claims, not evidence. Commands below were run against a `git archive HEAD`
tree at `/tmp/searcher-r5-grade` (the worktree is a sparse checkout; a missing
path here is not evidence the file is absent).

§39 terminal status: **NOT_READY**.

No critical §38.2 dimension reaches 90. Authenticity safety fell: `r3pl1ca`
is now caught, but a Turkish-dotless-i spelling of the same word, plus
`not 100% authentic` and `un-authorized`, still publish as Real. The cited
multi-view separation of +0.690816 does not reproduce. A default API campaign
still does not account for 24 sources. Photographs of a known KIND listing
still do not return that listing. §40 behaviour 15 is not met.

---

## Round-5 scores

Round 4 scored `4610edd` / `31e6004` (see `docs/grading/ROUND_4.md`). This
pass scores `4fae9f7`.

| Dimension | R4 | **This pass** | One-line justification |
|---|---:|---:|---|
| Plan fidelity | 82 | **85** | Contradiction-across-pairs, replica leet family, searx health, broker skip map, walk note, and §39 filenames are in the tree (`uv run python /tmp/searcher-r5-evidence/verify_claims.py`). §40.15, known-item retrieval, `ontology_for(None)`, and API-default coverage of 24 sources are not. |
| Implementation completeness | 84 | **86** | Colour/construction contradictions survive best-of-N; `LOCAL_CORRESPONDENCE` reports available when OpenCV is present; a default live campaign finished `rebag` as `SEARCHED_MATCHES_FOUND`. `ontology_for(None)` is still footwear; the API plan is 9 names, not 24. |
| Real-runtime proof | 76 | **78** | Independent live API + two campaigns ran. Floor suite **13 failed, 554 passed, 6 skipped, 1 deselected, 26 errors in 598.84s** (`uv run pytest -q --tb=line`); soak/abuse never started (`API process exited -11`). |
| User-visible proof | 87 | **88** | Pages HTTP **200** (11322 bytes). Live Willy search published **5** Possibly Real KIND cards whose URLs returned **200**, plus a walk note. Real remains empty. Trainer flagship published nothing. |
| Retrieval quality | 72 | **73** | `uv run python -m benchmark --all` without weights: recall@1 **0.914286**, false Real **0**. DINOv2 **0.771429** was not reproduced. Live known-item rank of `8001001141404` is **absent**. Honest pair-separation is **+0.010601**, not +0.690816. |
| Authenticity safety | 89 | **85** | `r3pl1ca` / Cyrillic / spaced / mixed-digit family cannot publish Real. A footwear true match can. `replıca` (U+0131), `not 100% authentic`, and `un-authorized` published **Real**. |
| Security and privacy | 82 | **86** | `./scripts/scrub_public_tree.sh` **PASS: working tree is clean**. SSRF refuses loopback. Isolated SSRF/API security tests passed. Abuse/soak did not run. History is still dirty. |
| Cost efficiency | 83 | **84** | API plan drops searx. Default live campaign completed `rebag` instead of spending 20s to `SOURCE_UNAVAILABLE`. 95705 ms median was not re-measured. Live-check still dominates. |
| Test quality | 83 | **84** | Targeted claim tests **131 passed, 1 skipped in 11.75s**. Isolated spawn-sensitive units **46 passed in 1.05s**. Property tests generate the ambiguous-digit class. Floor suite is not green in one process. Novel Real leaks have no test. |
| Documentation | 80 | **85** | Every Bible §39 filename and receipt exists (`verify_claims.py` §39 section). Real-scope commands in `SEARCHER_LIMITATIONS.md` reproduce. Release-readiness still quotes the round-2 scores. DINOv2 0.771 is cited and was not regenerated here. |

Critical floor is 90 (§38.2): plan fidelity, implementation completeness,
real-runtime proof, security/privacy, authenticity safety, test quality.
A user-visible product wave also needs user-visible proof ≥ 90. None of
those cleared.

Anything below 90, what would raise it:

- **Plan fidelity (85):** a default API campaign must record all 24 registry
  names; §40.15 must be met on the named Dior trainer or dropped from the
  public claim; `ontology_for(None)` must stop applying footwear.
- **Implementation completeness (86):** same, plus the replica detector must
  fold U+0131 and hyphenated / “not 100%” authenticity denials.
- **Real-runtime proof (78):** `uv run pytest -q` green without SIGSEGV;
  soak/abuse actually start; `pytest -m live_campaign` pass.
- **User-visible proof (88):** at least one Real card on a live campaign
  whose photographs are of the published listing.
- **Retrieval quality (73):** reproduce DINOv2 recall@1 0.771 on this host;
  live rank-1 of `8001001141404` from its own photographs; report
  pair-separation over the whole negative set, not one colourway row.
- **Authenticity safety (85):** no self-declared replica string, including
  untested homoglyphs, may publish Real.
- **Security and privacy (86):** abuse/soak exercise a live API process.
- **Cost efficiency (84):** independent 3-run median on this host.
- **Test quality (84):** floor suite green in one process; generated cases
  for U+0131 / `not 100% authentic` / hyphenated unauthorized.
- **Documentation (85):** scorecard and release-readiness quote this pass;
  cited DINOv2 figures either regenerate or are labelled unreproducible
  without local weights.

---

## Floor commands

| Command | Result |
|---|---|
| `uv run pytest -q --tb=line` | **13 failed, 554 passed, 6 skipped, 1 deselected, 26 errors in 598.84s**. Failures and errors are spawn `SIGSEGV` (-11) after tesseract / child `python` (`test_first_run`, `test_serve_shared`, `test_probe_and_import`, abuse/soak, crash-resume migrate). Log: `/tmp/searcher-r5-grade/artifacts/grading-round5/pytest.log`. |
| Isolated spawn-sensitive units | **46 passed in 1.05s** (`test_first_run`, `test_serve_shared`, `test_probe_and_import`, `test_ssrf_matrix`, `test_api_security`). |
| Targeted claim tests | **131 passed, 1 skipped in 11.75s** (contradiction, multiview, replica phrases/publication/routing, broker skips, robots catalog, keyhole note, real-gate, publication invariants, capability honesty, docs-match, known-item offline). The skip is `test_known_item_ranked_first_and_negative_is_not_real` (`local embedding weights are not installed` / no torch in this venv). |
| `uv run ruff check src tests benchmark` | `All checks passed!` |
| `uv run mypy src` | `Success: no issues found in 269 source files`. |
| `uv run python -m benchmark --all` | Isolated tree `/tmp/searcher-r5-bench`. Scorer `searcher.cheap_visual.ahash_colour`. recall@1 **0.914286**, recall@5 **1.0**, MRR **0.940476**, n **35**, false Real **0**, bucket precision **1.0** in every lane. Log: `artifacts/grading-round5/benchmark-all.log`. |
| `python3 scripts/flagship_acceptance.py --help` | Usage printed, exit 0. `./scripts/flagship_acceptance.py --help` is **exit 126** (`permission denied`: mode `rw-r--r--`). |
| `./scripts/scrub_public_tree.sh` | Exit **0**. `PASS: working tree is clean`. History still has `$HOME` / home-path hits; those do not fail the gate. |

---

## Claim checks

Each claim was run through something that would fail if it were false.

### 1. Multi-view pairing: identity takes the best pair; contradictions are collected across every considered pair

**Command.** `uv run pytest -q tests/unit/test_contradiction_across_pairs.py tests/unit/test_multiview_negatives.py` and
`uv run python /tmp/searcher-r5-evidence/measure_separation.py`.

| Case | item-match lower | hard contradictions |
|---|---:|---|
| `true_match` | 0.910000 | none |
| `authentic_poor_photos` | 0.804228 | none |
| `different_colourway` / `_multiview` | 0.120000 | `colourway-hard-mismatch` |
| `ai_generated` / `_multiview` | 0.120000 | `eyelet-count-mismatch`, `panel-count-mismatch` |
| `adjacent_model` / `_multiview` | 0.120000 | construction / logo |
| `counterfeit_excellent_photos` (1 view) | **0.793627** | **none** |
| `counterfeit_excellent_photos_multiview` | 0.120000 | `label-code-mismatch` |
| `different_season` (1 view) | 0.765028 | none |
| `different_season_multiview` | **0.876733** | none |

Colourway and AI no longer lose their contradiction when extra photographs
are added. Adding views to a different-season item still **raises** it, and
a one-view close counterfeit still has no match-level hard contradiction.

**Verdict.** The pairing rule **holds** for colour and construction. It does
**not** hold as “adding photographs cannot inflate a wrong item.”

### 2. Separation +0.690816 (was −0.099184)

**Command.** `uv run python /tmp/searcher-r5-evidence/measure_separation.py`

Claimed arithmetic is `authentic_poor_photos 0.810816 − different_colourway_multiview 0.120000 = 0.690816`.
Measured:

- weakest positive (`authentic_poor_photos`) = **0.804228**, not 0.810816
- strongest `NEGATIVE_PARENTS` row that is not labelled `possibly_real` =
  `counterfeit_excellent_photos` **0.793627**
- separation = **+0.010601**, not +0.690816
- if `different_season_multiview` (a `NEGATIVE_PARENTS` member) is included:
  **0.804228 − 0.876733 = −0.072505**

`matches_claimed_0.690816` is false.

**Verdict.** **FAIL.** The number is a cherry-picked pair, and even that
pair’s positive leg does not reproduce.

### 3. Replica detection: `r3pl1ca` and family, including Cyrillic + digit 1, and the word spaced out

**Command.** `uv run python /tmp/searcher-r5-evidence/verify_claims.py` and
`uv run pytest -q tests/unit/test_replica_phrases.py`.

| Text | `self_declared_replica` |
|---|---|
| `r3pl1ca` / `rep11ca` / `r3p1ica` | true |
| `repliсa` (Cyrillic es) / `r3pl1сa` | true |
| `r e p l i c a` / `r 3 p l 1 c a` | true |
| `re\u200bplica` | true |
| `not legit` / `god batch` / `dup` | true |
| `faux fur` / copy of the original receipt | false |

Forced through `published_public_bucket` with a Real decision, `r3pl1ca`
publishes `replica`. Routed under `matching-1` it is `hidden` /
`SELF_DECLARED_REPLICA`.

**Verdict.** The **claimed family holds**.

### 4. searx was advertised as reachable while pointing at loopback

**Command.** same `verify_claims.py`.

```text
SearxAdapter().endpoint          == ""
health.last_outcome              == SOURCE_UNAVAILABLE
"searx" in uncredentialed_source_names() == False
assert_url_safe("http://127.0.0.1:8080/search")
  -> SsrfBlocked: [POLICY] literal address 127.0.0.1 is blocked
assert_url_safe("http://localhost:8080/search")
  -> SsrfBlocked: [POLICY] hostname localhost is blocked
assert_url_safe("http://[::1]/search")
  -> SsrfBlocked: [POLICY] literal address ::1 is blocked
```

`SourceBroker().plan()` still **plans** searx (it is enabled and admitted;
health is not consulted unless a `HealthStore` is passed). The API plan
drops it.

**Verdict.** The product no longer counts searx as reach. The default
broker still plans a source that cannot answer.

### 5. A default run accounts for all 24 known sources

**Command.** `verify_claims.py` plus the live campaign
`45b5988b-3ab3-4c36-8d63-fe8fea95b023`.

`len(DEFAULT_ORDER)` is 24.
`SourceBroker().plan([en query])` → **10 planned, 14 skipped, 0 missing**.
Skips: ebay/etsy `AUTH_REQUIRED`; the other twelve `BLOCKED_BY_POLICY`.
The ten planned include **searx**.

`uncredentialed_source_names()` → **9 names** (searx dropped).
`SourceBroker(names=those 9).plan()` → 9 planned, **0 skipped recorded**,
**15 names absent** from coverage.

The live API campaign’s coverage listed 2 completed + 7 blocked = **9**.
ebay, etsy, searx, and the twelve disabled marketplaces were not named.

**Verdict.** **HOLD** for `SourceBroker()` with `DEFAULT_ORDER`. **FAIL**
for the default API campaign, which is what a user actually runs.

### 6. A source whose robots disallows `/search` is reported as walked

**Command.** `uv run pytest -q tests/unit/test_keyhole_coverage_note.py`
and the live campaign above.

`KindAdapter().manifest().capabilities` has `listing_fetch`, `live_check`,
not `text_search`. The projected note is:

> kind was walked through its catalogue instead of being searched. …

Live campaign note (this host, this SHA):

> rebag and kind were walked through their catalogues instead of being
> searched. Coverage was bounded to 42 pages and 48 candidates, so
> absence is not evidence of absence.

Coverage status for both is still `SEARCHED_MATCHES_FOUND`.

**Verdict.** The note **holds**. The outcome enum still says searched.

---

## The five places this pass was expected to be wrong

### 1. Real is reachable only for designer footwear, and is documented that way

**Commands.**

```bash
git ls-tree -r --name-only HEAD fixtures/calibration
uv run python -c "from searcher.authenticity.calibration import locate_default_table, load_table, table_applies; t=load_table(locate_default_table()); print(t.profile, table_applies(t,'handbag'), t.method, t.provenance)"
uv run python -c "from searcher.authenticity.calibration import apply_calibration; iv,cal,tag=apply_calibration(1.0, None); print(iv.lower_bound, cal, tag)"
uv run python -c "from searcher.ranking.policy_versions import load_policy; p=load_policy('matching-1'); print(p.require_calibrated_for_real, p.real.authenticity_lower_bound, p.real.item_match_lower_bound)"
uv run pytest tests/unit/test_real_gate_inputs.py::test_footwear_true_match_can_still_be_real -q
uv run python /tmp/searcher-r5-evidence/real_gate.py
```

Observed: one table, `fixtures/calibration/footwear_v1.json`.
`designer_footwear False` for a handbag. Uncalibrated raw 1.0 → lower
**0.78**, tag `uncalibrated`. `matching-1` requires calibrated Real and
authenticity ≥ 0.80, item-match ≥ 0.90. Footwear true-match fixture
publishes **Real** (item 0.91, auth 0.80, `fixture-calibrated:fixture-v1`).
A garment with the same pixels publishes **Possibly Real**, ceiling
`uncalibrated`. The table records `not_field_calibrated: true`, `n: 24`.
`SEARCHER_LIMITATIONS.md` states this and the commands reproduce.

**Verdict.** **True, and honestly documented.** Footwear Real rests on 24
synthetic fixtures, which the docs say.

### 2. `scripts/known_item_check.sh` FAIL — photographs of a known KIND listing do not return that listing

**Command.** Live POST of
`fixtures/known_item_kind/images/8001001141404_{1,2,3}.jpg` to a
`searcher serve` on `127.0.0.1:8799` with text `Willy Chavarria black long
sleeve`. Same assertion as the script: target handle in Real or Possibly
Real.

Independent run, search `45b5988b-3ab3-4c36-8d63-fe8fea95b023`, 121 s,
terminal `PARTIAL`:

| Field | Observed |
|---|---|
| Real | **[]** |
| Possibly Real | 5 KIND URLs, **none** `8001001141404` |
| First published | `https://shop.kind.co.jp/products/8006002318626` (HTTP **200**) |
| Target rank | **absent** |

The committed `artifacts/realmatch/known_item_summary.json` says the same
(`target_in_real_rank: null`, `target_in_possibly_real_rank: null`).

The script was not executed as `./scripts/known_item_check.sh` because it
requires `uv run --extra vision` and a weights download. The assertion it
would make was run against the same photographs and the same API.

**Verdict.** **Confirmed FAIL.**

### 3. §40 behaviour 15 — run the flagship acceptance script and report the count

**Commands.** `python3 scripts/flagship_acceptance.py --help` (exit 0).
Then the same script against the live API with the three first-run trainer
PNGs and the script’s default Dior text. The process died in
`browser_processes()` (`ps`: Operation not permitted). The campaign had
already finished. Re-evaluated with `evaluate()` and `browser_processes`
stubbed to 0:

Independent trainer + Dior text, search `a4c479dc-a931-49db-9a96-d1d134053b58`:

```text
met 10, not met 4, not evaluable 10, of 24
15 not met   high-evidence candidates appear in Real | Real=0
16 not met   plausible but incomplete appear in Possibly Real | Possibly Real=0
```

Events were not captured (the crash was after `wait_terminal`), so
behaviours 4 and 6 are under-counted relative to a clean script run.

Committed receipts at this SHA, not re-run:

| Receipt | input | met / not met / n.e. | Real | behaviour 15 |
|---|---|---|---:|---|
| `artifacts/searcher-flagship-matched.receipt.json` | Willy garment | 20 / 1 / 3 | 0 | not met |
| `artifacts/searcher-flagship-acceptance.receipt.json` | Dior text, KIND photos | 13 / 3 / 8 | 0 | not met |

**Verdict.** Behaviour 15 is **not met**. Best committed count is **20 / 1 / 3**.
This host’s trainer run is **10 / 4 / 10** with Real=0.

### 4. Attack the replica detector and the Real gate with obfuscations nobody has written a test for

**Command.** `uv run python /tmp/searcher-r5-evidence/attacks.py` (88
strings not in `test_replica_phrases.py`) and `real_gate.py` (real
`match_candidate` + `route_candidate` + `published_public_bucket`).

Reached **Real** on a calibrated footwear true-match (item 0.91, auth 0.80):

| Title suffix | detected | published |
|---|---|---|
| `r3pl1ca` | true | replica |
| `replıca` (U+0131) | **false** | **real** |
| `not 100% authentic` | **false** | **real** |
| `un-authorized` | **false** | **real** |

`attacks.py` additionally missed detection (and would force-publish Real)
for, among others: `notlegit`, `not_legit`, `counter–feit` (en-dash),
`inspired-by`, `pk-god`, `f a k e`, `l:l quality`, Indonesian `kw` /
`kopi`. Some of those are slang the project never claimed. The three
Real leaks above are the same claim in other letters.

Uncalibrated perfect scores cannot satisfy Real (`garment_true_pixels`
→ Possibly Real). That half of the gate holds.

**Verdict.** The claimed family is closed. The detector is not closed.
Replica language reached **Real**.

### 5. Whether any number in the §39 documents is not reproducible on this host

Reproduced on this host:

| Number | Where | Command | This host |
|---|---|---|---|
| uncalibrated lower 0.78 | `SEARCHER_LIMITATIONS.md` | `apply_calibration(1.0, None)` | 0.78 |
| Real auth gate 0.80, item 0.90 | same | `load_policy('matching-1')` | 0.80 / 0.90 |
| ahash recall@1 0.914286 | `SEARCHER_PUBLIC_BENCHMARK_REPORT.md` | `python -m benchmark --all` | 0.914286 |
| ahash crop recall@1 0.4 | same (noweights receipt) | same | 0.4 |
| false Real 0 / precision 1.0 | public benchmark report | same | 0 / 1.0 |
| shipped 0.86 held-out FPR 0.7 | public benchmark report | receipt file, not regenerated | cited only |
| pair-calibration median 0.8101, TPR@0.90 0.237 | same | receipt file, not regenerated | cited only |

Not reproduced:

| Number | Where | This host |
|---|---|---|
| DINOv2 recall@1 0.771429 / MRR 0.866667 | `CLAIMS.md`, public benchmark report, Pages copy | no torch in the project venv; scorer fell back to ahash |
| live median 95704.578 ms | `SEARCHER_PERFORMANCE_BASELINE.md` | not re-run |
| authentic_poor 0.810816, separation +0.690816 | commit message only, not a §39 file | 0.804228 / +0.010601 |
| fixture-campaign 49.069 / 29.266 ms | performance baseline | not re-run |

`SEARCHER_PUBLIC_BENCHMARK_REPORT.md` already says the DINOv2 figures
require local weights. The number is still the one `CLAIMS.md` and
`web/index.html` quote (`test_docs_match_capabilities.py` binds 0.771).

**Verdict.** The DINOv2 headline and the live wall-time median are **not**
reproducible on this host in this session. The ahash headline and the
calibration-gate numbers **are**.

---

## Four attacks (this pass)

### Attack A — publish a replica to Real

Calibrated footwear true-match, `matching-1`, destination verified.

- `r3pl1ca` → published `replica`
- `replıca` (U+0131) → published **Real**
- `not 100% authentic` → published **Real**
- `un-authorized` → published **Real**

**Outcome.** Failed on the claimed family. Succeeded on three untested
spellings. `SEARCHER_BUCKET_POLICY.md` forbids a replica listing on either
public tab.

### Attack B — put a garment or an uncalibrated listing in Real

Garment, complete views, same pixels as the shoe fixture: Possibly Real,
`authority_ceiling=uncalibrated`, auth lower 0.5163. Uncalibrated raw 1.0
is 0.78 against a 0.80 gate, then clamped another 0.01.

**Outcome.** Blocked.

### Attack C — make a capability lie

`GET /v1/capabilities` on the live process (OpenCV installed, no
`embedding.pt` in this venv):

| Lane | available | lie? |
|---|---|---|
| `DENSE_FEATURES` | false, “No local embedding weights” | no |
| `LOCAL_CORRESPONDENCE` | **true**, ORB note | no (R4 lie is closed) |
| `NEXT_VIEW` | true, “Searcher-owned missing-evidence heuristic” | advertised; labelled as a heuristic |
| `OCR` | true, tesseract | matches the process that later SIGSEGV-spawns |

**Outcome.** The R4 correspondence denial is closed.

### Attack D — default campaign coverage of 24 sources

Live campaign coverage contained 9 source ids. Fifteen members of
`DEFAULT_ORDER` were unnamed.

**Outcome.** The broker-level claim holds. The product-level claim does not.

---

## §39 terminal deliverables

Present at the exact Bible names (this SHA):

- `SEARCHER_SOURCE_AUTHORITY.md`, `SEARCHER_REUSE_LEDGER.json`,
  `SEARCHER_ARCHITECTURE.md`, `SEARCHER_DATA_MODEL.md`,
  `SEARCHER_SOURCE_POLICY.md`, `SEARCHER_AUTHENTICITY_POLICY.md`,
  `SEARCHER_BUCKET_POLICY.md`, `SEARCHER_UX_SPEC.md`,
  `SEARCHER_SECURITY.md`, `SEARCHER_PRIVACY.md`,
  `SEARCHER_PERFORMANCE_BASELINE.md`, `SEARCHER_BENCHMARK_METHOD.md`,
  `SEARCHER_PUBLIC_BENCHMARK_REPORT.md`, `SEARCHER_LIMITATIONS.md`,
  `SEARCHER_RELEASE_READINESS.md`, `SEARCHER_FINAL_SCORECARD.md`,
  `SEARCHER_TERMINAL_REPORT.md`
- `artifacts/searcher-source-authority.receipt.json`,
  `artifacts/searcher-reuse-ledger.receipt.json`,
  `artifacts/searcher-clean-clone.receipt.json`,
  `artifacts/searcher-security.receipt.json`,
  `artifacts/searcher-performance.receipt.json`,
  `artifacts/searcher-public-benchmark.receipt.json`,
  `artifacts/searcher-terminal.receipt.json`

R4’s missing-name list is closed. The terminal report and scorecard still
bind SHA `31e6004` and quote the round-2 / round-4 grades; they are not a
self-grade of `4fae9f7`.

---

## STATUS

NOT_READY.

No critical §38.2 score is ≥ 90. Behaviour 15 is not met. Replica
language reached Real. Known-item photographs do not retrieve the listing.
The cited +0.690816 separation is not a measurement of the corpus.

## CLAIMS

1. Multi-view identity = best pair, contradictions = all considered pairs:
   **HOLD** for colour and construction; **FAIL** as a general “more
   photographs cannot inflate a wrong item” (`different_season_multiview`
   0.876733 > `authentic_poor_photos` 0.804228).
2. Separation +0.690816: **FAIL** (measured +0.010601; 0.810816 does not
   reproduce).
3. `r3pl1ca` family including Cyrillic + digit 1 and spacing: **HOLD**.
4. searx no longer advertised as reach while on loopback: **HOLD** on the
   API plan; broker default still plans it.
5. Default run accounts for all 24 sources: **HOLD** for
   `SourceBroker().plan()`; **FAIL** for the default API campaign (9 of 24).
6. Robots-`/search` source reported as walked: **HOLD** (live note present;
   status still `SEARCHED_MATCHES_FOUND`).
7. Real only for designer footwear, honestly documented: **HOLD**.
8. `known_item_check` photographs miss the listing: **HOLD** (independent
   live miss).
9. §40 behaviour 15: **FAIL** (Real=0 on every scored campaign).

## EVIDENCE

Commands that would fail if the supporting sentence were false:

- `uv run pytest -q --tb=line` → 13 failed, 554 passed, 6 skipped, 1
  deselected, 26 errors in 598.84s
- `uv run python -m benchmark --all` → recall@1 0.914286, false Real 0
- `uv run python /tmp/searcher-r5-evidence/verify_claims.py`
- `uv run python /tmp/searcher-r5-evidence/measure_separation.py`
- `uv run python /tmp/searcher-r5-evidence/attacks.py`
- `uv run python /tmp/searcher-r5-evidence/real_gate.py`
- live POST of `8001001141404_{1,2,3}.jpg` → search
  `45b5988b-3ab3-4c36-8d63-fe8fea95b023`, target absent, walk note present
- `python3 scripts/flagship_acceptance.py` + re-`evaluate` → 10 / 4 / 10,
  behaviour 15 not met
- `curl -sS -o /dev/null -w '%{http_code}' https://joshuahickscorp.github.io/searcher/` → 200
- `curl -sS -I https://shop.kind.co.jp/products/8006002318626` → 200
- `./scripts/scrub_public_tree.sh` → PASS: working tree is clean
- `uv run ruff check src tests benchmark` → All checks passed
- `uv run mypy src` → 269 files, no issues

Machine-readable traces live under `/tmp/searcher-r5-grade/artifacts/grading-round5/`
(not committed; this pass may write only this file).

## CHANGES

This lane wrote only `docs/grading/ROUND_5.md`. `src/`, `tests/`,
`benchmark/`, and the rest of the tree were read via `git show` /
`git archive` and were not edited.

## TESTS

See Floor commands. Claim, replica, broker, walk-note, and real-gate tests
passed in isolation. The one-process floor suite did not. Soak and abuse
never started.

## RISKS

- SIGSEGV on `subprocess` after tesseract / `searcher serve` (same G039
  class as rounds 2–4). Isolated re-run of the same tests is green.
- `ps` is forbidden in this sandbox, so
  `scripts/flagship_acceptance.py` cannot finish unattended.
- `./scripts/flagship_acceptance.py` is not executable.
- Default API coverage still hides 15 of 24 registry names, so a reader
  cannot tell blocked from unmentioned.
- Replica homoglyph coverage is an open list. This pass reached Real
  without using any string the unit tests already contain.

## UNRESOLVED

- Nothing live reaches Real. §40.15 is not met.
- Known KIND photographs do not retrieve that listing.
- +0.690816 is not a corpus separation.
- `replıca` / `not 100% authentic` / `un-authorized` publish Real.
- API default campaign does not account for 24 sources.
- Floor suite is not green in one process.
- DINOv2 0.771 not reproduced without torch + weights.
- `ontology_for(None)` still returns footwear.
- Soak/abuse still force `SEARCHER_LIVE_DISCOVERY=0` and then fail to
  spawn the API process in a one-process suite.

## NEXT

Smallest path to a status other than `NOT_READY`:

1. Fold U+0131, hyphenated `un-authorized`, and `not 100% authentic` into
   `self_declared_replica` and the generated property test. Re-attack with
   strings that are not in the suite.
2. Make the default API campaign record every `DEFAULT_ORDER` name
   (planned or skipped). Stop calling a catalogue walk
   `SEARCHED_MATCHES_FOUND` without the walk note — the note is there;
   the enum is not.
3. Either retrieve `8001001141404` from its own photographs into a public
   tab, or stop claiming known-item recall.
4. Keep `./scripts/test_all.sh` from sharing an interpreter with tesseract
   / `searcher serve` (the live-campaign split already exists; the fast
   suite now needs the same).
5. Put one live designer-footwear item in Real, or drop §40.15 from the
   claim ceiling.

Until 1–4 are independently re-run and the critical scores are ≥ 90,
the terminal status stays `NOT_READY`.
