# Round 6 independent regrade

Graded 2026-08-17 against Bible §38 / §39 at commit
`72cc839843975f08189612e942f1a44650a506b1`. This pass did not write `src/`,
`tests/`, `benchmark/`, `scripts/`, `web/`, `fixtures/`, or `pyproject.toml`.
Commit messages, `SEARCHER_FINAL_SCORECARD.md`, and this contract were treated
as claims, not evidence.

The worktree is a sparse checkout. Commands below were run against a
`git archive HEAD` tree at `/tmp/searcher-r6-grade` using the parent venv at
`<repo>/.venv`. A path missing from this
worktree is not evidence the file is absent.

§39 terminal status: **NOT_READY**.

No critical §38.2 dimension reaches 90. The named replica strings from
round 5 now cannot publish Real. Equivalent claims that nobody tested —
`isn't 100% authentic`, `not–authentic` (en-dash), `re–plica`, Greek iota
`replιca`, `non-authentic` — still publish as Real. A live API campaign
now names all 24 registry sources. Photographs of KIND listing
`8001001141404` still do not return that listing. §40 behaviour 15 is
not met. Real remains empty on the live path.

---

## Round-6 scores

Round 5 scored `4fae9f7` (see `docs/grading/ROUND_5.md`). This pass scores
`72cc839`.

| Dimension | R5 | **This pass** | ≥90? | Command that would fail if the score’s fact were false |
|---|---:|---:|:---:|---|
| Plan fidelity | 85 | **88** | no | `python /tmp/searcher-r6-evidence/verify_claims.py` (24 names, `ontology_for(None)` not footwear) and live search `515e5362` coverage = 24. Still open: §40.15, known-item miss, `source_limit=8` against 9 answerable names. |
| Implementation completeness | 86 | **88** | no | Same verify script + `python /tmp/searcher-r6-evidence/both_engines_standalone.py` (both engines keep later sources). One calibration table; `source_limit=8` still hardcoded in `api_campaign.py`. |
| Real-runtime proof | 78 | **79** | no | `python -m pytest -q --tb=line` → **16 failed, 585 passed, 3 skipped, 1 deselected, 26 errors in 559.28s**. Independent live campaign `515e5362` finished PARTIAL in 85.6s. Soak/abuse never started (`API process exited -11`). |
| User-visible proof | 88 | **89** | no | `curl -sS -o /dev/null -w '%{http_code} %{size_download}' https://joshuahickscorp.github.io/searcher/` → **200 11322**. Live campaign published **6** Possibly Real KIND cards (first URL HTTP **200**), Real **[]**, walk note present. |
| Retrieval quality | 73 | **73** | — | `python -m benchmark --all` → recall@1 **0.914286**, scorer `searcher.cheap_visual.ahash_colour`, false Real **0**. Live rank of `8001001141404` is **absent**. DINOv2 0.771429 was not reproduced. |
| Authenticity safety | 85 | **86** | no | Claimed family: `self_declared_replica('replıca')` etc. is True; those titles publish `replica`. Novel same-claim strings publish **real** (`python /tmp/searcher-r6-evidence/real_publish.py` → 18 Real leaks). |
| Security and privacy | 86 | **86** | no | `./scripts/scrub_public_tree.sh` → **PASS: working tree is clean**. `pytest tests/security/test_ssrf_matrix.py tests/security/test_api_security.py` → **29 passed**. Abuse/soak `-11`. History still has `$HOME` hits. |
| Cost efficiency | 84 | **84** | — | Live campaign wall **85.6s**, 52 pages on `kind`, `source_limit=8`. 95705 ms median was not re-measured. `archive_org` is `UNMEASURABLE` because the ninth answerable source does not fit the budget. |
| Test quality | 84 | **85** | no | `python -m pytest tests/mutation -q -s` → **11 passed**, all 11 sabotages **KILLED**. Targeted claim tests **95 passed**. Floor suite not green. Novel Real leaks have no test. Bible §32.9 item 12 is absent. |
| Documentation | 85 | **85** | — | Every §39 filename exists (`ls` of the 17 names + 7 receipts). Limitations commands for Real-scope reproduce. Scorecard still stops at `4610edd`. Pages copy still quotes DINOv2 0.771. |

Critical floor is 90 (§38.2): plan fidelity, implementation completeness,
real-runtime proof, security/privacy, authenticity safety, test quality.
A user-visible product wave also needs user-visible proof ≥ 90.

| Critical dimension | Score | At or above 90? |
|---|---:|:---:|
| Plan fidelity | 88 | **no** |
| Implementation completeness | 88 | **no** |
| Real-runtime proof | 79 | **no** |
| Security and privacy | 86 | **no** |
| Authenticity safety | 86 | **no** |
| Test quality | 85 | **no** |
| User-visible proof (user-visible wave) | 89 | **no** |

None of those cleared.

Anything below 90, what would raise it:

- **Plan fidelity (88):** retrieve `8001001141404` into a public tab, or drop
  the known-item claim; meet §40.15 or drop it; raise `source_limit` to the
  answerable set (9) or stop planning 9.
- **Implementation completeness (88):** same, plus close the replica class
  (contractions, en-dash, remaining homoglyphs) rather than the last listed
  spellings.
- **Real-runtime proof (79):** `python -m pytest -q` green without SIGSEGV;
  soak/abuse actually start.
- **User-visible proof (89):** at least one Real card on a live campaign
  whose photographs are of the published listing.
- **Retrieval quality (73):** live rank-1 of `8001001141404`; reproduce
  DINOv2 recall@1 0.771 on a host with weights, or stop citing it as the
  headline.
- **Authenticity safety (86):** no self-declared replica phrasing, including
  `isn't 100% authentic` and en-dash / Greek-iota forms, may publish Real.
- **Security and privacy (86):** abuse/soak exercise a live API process.
- **Cost efficiency (84):** independent 3-run median; do not leave the ninth
  answerable source `UNMEASURABLE` solely because `source_limit=8`.
- **Test quality (85):** floor suite green in one process; generated cases
  for the novel Real leaks; the 12th Bible sabotage (`expose hidden
  benchmark answer`) either exists and is killed or is explicitly retired.
- **Documentation (85):** scorecard quotes this pass; cited DINOv2 figures
  either regenerate or stay labelled as weights-only.

---

## Floor commands

| Command | Result |
|---|---|
| `python -m pytest -q --tb=line` (archive tree, equivalent to `uv run pytest -q`) | **16 failed, 585 passed, 3 skipped, 1 deselected, 26 errors in 559.28s**. 18 `Fatal Python error: Segmentation fault` in tesseract / child spawn. Abuse/soak: `API process exited -11`. Log: `/tmp/searcher-r6-grade/artifacts/grading-round6/pytest.log`. |
| Isolated spawn-sensitive units | **19 passed in 1.67s** (`test_first_run`, `test_serve_shared`, `test_probe_and_import`). |
| Isolated budget-exhaustion tests | **2 passed in 0.37s** (`tests/unit/test_budget_exhaustion_is_reported.py`). The same file **FAILED** inside the one-process floor suite (`archive_org` was `UNMEASURABLE`, not `NOT_ATTEMPTED`) after `install_bounded_discovery()` rebound the class. |
| Targeted claim tests | **95 passed in 1.21s** (budget, 24-source API, replica phrases/publication, ontology, real-gate, docs-match). |
| `python -m pytest tests/mutation -q -s` | **11 passed in 0.37s**. All 11 sabotages **KILLED**. |
| `python -m ruff check src tests benchmark` | `All checks passed!` |
| `python -m mypy src` | `Success: no issues found in 269 source files`. |
| `python -m benchmark --all` | Scorer `searcher.cheap_visual.ahash_colour` (no weights). recall@1 **0.914286**, recall@5 **1.0**, MRR **0.940476**, n **35**, false Real **0**. Separation this host: over_different_item **+0.684228**, over_every_negative **−0.105772**. Overwrites the local receipt; HEAD still cites DINOv2. |
| `./scripts/flagship_acceptance.py --help` | Usage printed, **exit 0**. Mode `100755`. |
| `./scripts/scrub_public_tree.sh` | Exit **0**. `PASS: working tree is clean`. History still has `$HOME` / home-path hits; those do not fail the gate. |

Failures inside the one-process floor suite (for the record, not all of them
are product defects):

- spawn SIGSEGV (`test_first_run`, `test_serve_shared`, `test_probe_and_import`,
  crash-resume, orchestrator-sigkill, abuse/soak) — isolated re-run is green
- `test_budget_exhaustion_mid_source_still_reports_every_planned_source` —
  assertion written for sequential `NOT_ATTEMPTED`; rebound Bounded engine
  records `UNMEASURABLE` (sources are still named)
- `test_docs_match_capabilities` `0.914 == 0.771` — this pass’s
  `benchmark --all` rewrote the archive receipt to the fallback scorer;
  `git show HEAD:artifacts/searcher-public-benchmark.receipt.json` still
  has DINOv2 0.771429
- `test_rendering_fetcher.py::test_js_only_page_parses_under_renderer`

---

## Claim checks

Each claim was run through something that would fail if it were false.

### 1. The three round-5 Real leaks, plus `un_authorized` and `not-authentic`, are detected

**Command.**

```bash
python -c "from searcher.retrieval.text import self_declared_replica; \
  xs=['replıca','not 100% authentic','un-authorized','un_authorized','not-authentic']; \
  print([(x, self_declared_replica(x)) for x in xs]); \
  raise SystemExit(0 if all(self_declared_replica(x) for x in xs) else 2)"
python /tmp/searcher-r6-evidence/real_publish.py
```

| Title suffix | `self_declared_replica` | `published_public_bucket` of a Real decision |
|---|---|---|
| `replıca` (U+0131) | true | **replica** |
| `not 100% authentic` | true | **replica** |
| `un-authorized` | true | **replica** |
| `un_authorized` | true | **replica** |
| `not-authentic` | true | **replica** |
| `r3pl1ca` | true | **replica** |

**Verdict.** The **named family holds**. Those strings cannot publish Real.

### 2. Attack the detector with obfuscations nobody has written

**Command.** `python /tmp/searcher-r6-evidence/attacks.py` (66 novel strings
not present as literals in the replica / publication tests) and
`python /tmp/searcher-r6-evidence/real_publish.py` (force a calibrated Real
decision through `published_public_bucket`).

Reached **Real** (detected false, published `real`):

| Title suffix | Why it is the same claim |
|---|---|
| `isn't 100% authentic` | the patched phrase, with a contraction |
| `ain't 100% authentic` | same |
| `isn't fully authentic` | same hedge family |
| `not even authentic` / `not at all authentic` / `not really 100% authentic` | extra hedge the optional-one-word list does not include |
| `non-authentic` / `inauthentic` | negated authenticity |
| `not–authentic` / `un–authorized` / `re–plica` | en-dash, not `[\s._-]` |
| `re/plica` | slash separator |
| `r3pl!ca` | `!` is not in the digit-for-letter map |
| `replιca` (Greek iota U+03B9) | same homoglyph class as U+0131, not in `_HOMOGLYPHS` |
| `replӏca` (Cyrillic palochka, mapped to **l** not i) | becomes `repllca` |
| `ʀᴇᴘʟɪᴄᴀ` (small caps) | NFKC leaves them alone |
| `re\xadplica` (soft hyphen) | not stripped |
| `not authorized` | related; weaker (could be “not authorized dealer”) |

Slang the project never claimed (`kw`, `kopi`, `repz`, `l:l quality`) also
misses. Those are not counted as a broken product claim.

**Verdict.** **REFUTED** as “the detector is closed.” Replica language still
reaches Real. The three named leaks are closed; the class is not.

### 3. §32.9 mutation suite exists and all eleven sabotages are killed

**Command.** `python -m pytest tests/mutation -q -s`

```
KILLED    count duplicate images as independent
KILLED    disable live check
KILLED    map blocked source to no-match
KILLED    make price increase authenticity
KILLED    bypass hard contradiction
KILLED    move all candidates to Real
KILLED    skip receipt verification
KILLED    accept changed donor SHA
KILLED    omit search budget
KILLED    preserve browser process
KILLED    leak upload path
11 passed in 0.37s
```

Bible §32.9 also lists **expose hidden benchmark answer**. That twelfth
sabotage is not in `tests/mutation/test_specified_mutations.py`
(`python -c` count of `def test_mutation_` is 11; `"expose hidden" in suite`
is false).

**Verdict.** **HOLD** for the eleven the contract named. The Bible list is
12; the twelfth is absent.

### 4. §32.1 coverage floor is measured: only `matching` meets 90/80

**Command.**

```bash
python3 -c 'import json; d=json.load(open("artifacts/searcher-coverage-floor.receipt.json"));
print(d["measured_at_commit"], [(r["area"], r["statement"], r["branch"], r["meets_floor"]) for r in d["areas"]]);
assert [r["area"] for r in d["areas"] if r["meets_floor"]] == ["matching"]'
```

| Area | statement | branch | meets 90/80 |
|---|---:|---:|:---:|
| matching | 91.7 | 84.6 | yes |
| ranking | 91.4 | 72.0 | no |
| authenticity | 93.0 | 78.9 | no |
| api | 86.2 | 70.7 | no |
| campaigns | 80.1 | 62.5 | no |
| sources | 81.4 | 64.4 | no |
| retrieval | 86.9 | 71.5 | no |

Total 80.5 / 66.1. Receipt `measured_at_commit` is **`7a3f314`**, not
`72cc839`. The floor was measured; it was not remeasured at this SHA.
`./scripts/coverage_floor.sh` is the reproduce command. This pass did not
re-run it (it is another full pytest).

**Verdict.** **HOLD** as a statement about the committed measurement.
Stale relative to this SHA.

### 5. Budget exhaustion inside one source no longer loses the sources after it, in both engines

**Command.** Isolated
`python -m pytest tests/unit/test_budget_exhaustion_is_reported.py -q`
→ **2 passed**. Standalone
`python /tmp/searcher-r6-evidence/both_engines_standalone.py`:

```
classes ['DiscoveryEngine', 'BoundedDiscoveryEngine'] imported_is_bounded False
DiscoveryEngine          coverage={'wikimedia': SEARCHED_NO_MATCH, 'kind': UNMEASURABLE, 'archive_org': NOT_ATTEMPTED}  missing=[]
BoundedDiscoveryEngine   coverage={'wikimedia': SEARCHED_NO_MATCH, 'kind': UNMEASURABLE, 'archive_org': SEARCHED_NO_MATCH}  missing=[]
```

Both `run()` methods wrap `_run_plan` in `try/except BudgetExceeded`
(`python /tmp/searcher-r6-evidence/verify_claims.py`).

The same unit test **FAILED** inside the one-process floor suite:
`assert 'UNMEASURABLE' == 'NOT_ATTEMPTED'`. After
`install_bounded_discovery()`, the imported name is the parallel engine,
which does not leave later sources as `NOT_ATTEMPTED` because it already
started them. They are still **named**. Nothing vanished.

**Verdict.** **HOLD** for the product claim (no later source is omitted
from coverage). The suite’s sequential assertion is not true of the engine
the API actually runs.

### 6. A campaign accounts for all 24 known sources

**Command.**

```bash
python -c "from searcher.sources.broker import DEFAULT_ORDER; from searcher.workers.api_campaign import api_source_names, uncredentialed_source_names;
print(len(DEFAULT_ORDER), api_source_names()==list(DEFAULT_ORDER), len(uncredentialed_source_names()))"
# live: POST three 8001001141404 photographs, then
python3 -c 'import json; d=json.load(open("/tmp/searcher-r6-evidence/live_search.json"));
ids={r["id"] for k in ("sources_completed","sources_blocked","sources_in_progress") for r in d["coverage"][k]};
print(len(ids), sorted(ids)); assert len(ids)==24'
```

`DEFAULT_ORDER` is 24. `api_source_names()` returns that tuple.
`uncredentialed_source_names()` is 9 (searx dropped). Broker
`plan(..., skip_unanswerable=True)` accounts for 24 (9 planned, 15 skipped).

Independent live search `515e5362-3bb5-4870-92d1-da5a0e590e4c`:

- 1 completed: `kind` `SEARCHED_MATCHES_FOUND`
- 23 blocked, including `searx` `SOURCE_UNAVAILABLE`, `ebay`/`etsy`
  `AUTH_REQUIRED`, twelve `BLOCKED_BY_POLICY`, `archive_org` `UNMEASURABLE`
- **24 named**. Mid-run, before `account_for_every_known_source`, only 9
  were visible. After `PARTIAL`, all 24 were on the coverage map.

**Verdict.** **HOLD** for the default API campaign. Round 5’s product-level
fail is closed.

### 7. The benchmark receipt names its scorer, and separation is published on both bases

**Command.** `python -m benchmark --all` and
`git show HEAD:artifacts/searcher-public-benchmark.receipt.json`.

| | HEAD receipt | This host’s `--all` |
|---|---|---|
| `scorer.identity` | `facebookresearch.dinov2.vits14` | `perceptual-hash fallback` / `searcher.cheap_visual.ahash_colour` |
| `over_different_item_negatives` | +0.690816 | +0.684228 |
| `over_every_negative` | −0.099184 | −0.105772 |
| `weakest_positive` | 0.810816 | 0.804228 |
| recall@1 | 0.771429 | 0.914286 |

Both receipts contain `over_every_negative` and
`over_different_item_negatives`, and both name a scorer. The flattering
base is no longer alone. The committed 0.810816 / +0.690816 pair does not
reproduce on this host (weakest positive is 0.804228, as in round 5).

Recomputed from this run’s ten bucket rows:

```
weakest_positive 0.804228
over_every_negative -0.105772   (stolen_photos 0.91)
over_different_item  0.684228   (next negative 0.12)
```

**Verdict.** **HOLD**. Both bases are published. The headline DINOv2
figures remain unreproducible without weights.

### 8. `ontology_for(None)` is no longer footwear

**Command.**

```bash
python -c "from searcher.matching.ontology import ontology_for;
o=ontology_for(None); print(o.category, o.profile_id, o.part_names());
assert o.category!='footwear' and 'eyelets' not in o.part_names() and 'outsole' not in o.part_names()"
```

Observed: `uncategorised` / `generic:uncategorised` / `('subject',)`.
`ontology_for('shoe')` is still footwear. `ontology_for('garment')` is
garment. `pytest tests/unit/test_gap_views_by_category.py tests/unit/test_part_ontology.py`
→ **9 passed**.

**Verdict.** **HOLD**.

### 9. `./scripts/flagship_acceptance.py --help` exits 0

**Command.** `./scripts/flagship_acceptance.py --help` from this worktree
and from the archive.

Both print usage and exit **0**. `git ls-tree HEAD` mode is `100755`.

**Verdict.** **HOLD**. Round 5’s exit 126 (mode `644`) is closed.

---

## The places this pass was expected to still be weakest

I agree with all four. Independent evidence:

### Real is reachable only for designer footwear, because one calibration table ships

```bash
git ls-tree -r --name-only HEAD fixtures/calibration
# fixtures/calibration/footwear_v1.json
python -c "from searcher.authenticity.calibration import locate_default_table, load_table, table_applies, apply_calibration;
t=load_table(locate_default_table()); print(t.profile, table_applies(t,'handbag'));
print(apply_calibration(1.0, None))"
python -m pytest tests/unit/test_real_gate_inputs.py::test_footwear_true_match_can_still_be_real -q
```

One table. `designer_footwear False` for a handbag. Uncalibrated raw 1.0 →
lower **0.78**, tag `uncalibrated`. Footwear true-match fixture publishes
Real. `SEARCHER_LIMITATIONS.md` states this and the commands reproduce.

**True, and honestly documented.**

### §40.15 has never been met

Committed `artifacts/searcher-flagship-matched.receipt.json`: met 20 /
not met 1 / n.e. 3; behaviour 15 **not met**, Real=0.
`artifacts/searcher-flagship-acceptance.receipt.json`: 13 / 3 / 8;
behaviour 15 **not met**, Real=0.
This host’s live campaign `515e5362`: Real **[]**.

**Confirmed.** Behaviour 15 is not met.

### Known-item photographs do not retrieve their own listing

Live POST of `8001001141404_{1,2,3}.jpg` + text `Willy Chavarria black long
sleeve` to `searcher serve` on `127.0.0.1:8798`. Search
`515e5362-3bb5-4870-92d1-da5a0e590e4c`, 85.6s, terminal `PARTIAL`:

| Field | Observed |
|---|---|
| Real | **[]** |
| Possibly Real | 6 KIND URLs, **none** `8001001141404` |
| First published | `https://shop.kind.co.jp/products/8006002318626` (HTTP **200**) |
| Target listing | HTTP **200** at `https://shop.kind.co.jp/products/8001001141404` (the listing exists; the engine did not retrieve it) |
| Walk note | `kind was walked through its catalogue instead of being searched. Coverage was bounded to 52 pages and 24 candidates, so absence is not evidence of absence.` |
| kind status | still `SEARCHED_MATCHES_FOUND` |

**Confirmed FAIL.** Catalogue walk + `source_limit=8` is why.

### `source_limit=8` is hardcoded against 9 planned sources

```bash
rg -n "source_limit=8" src/searcher/workers/api_campaign.py src/searcher/core/budgets.py src/searcher/sources/live_runner.py
python -c "from searcher.workers.api_campaign import uncredentialed_source_names; print(len(uncredentialed_source_names()), uncredentialed_source_names())"
```

`source_limit=8 if cfg.live_discovery else 0` in `api_campaign.py:151`.
`Budget.fixture_default().source_limit == 8`. Live campaign: 9 answerable
names, `archive_org` `UNMEASURABLE`. That is the ninth source hitting the
ceiling, not a health skip.

**Confirmed.**

I would add a fifth weakness the contract did not name: the replica
detector is still an open list. Closing three spellings did not close
the claim.

---

## Four attacks (this pass)

### Attack A — publish a replica to Real

Calibrated Real decision, `matching-1`, usable `https` link, through
`published_public_bucket`.

- `r3pl1ca` / `replıca` / `not 100% authentic` / `un-authorized` /
  `un_authorized` / `not-authentic` → published **replica**
- `isn't 100% authentic` → published **Real**
- `not–authentic` (en-dash) → published **Real**
- `re–plica` / `replιca` / `non-authentic` → published **Real**

**Outcome.** Failed on the named family. Succeeded on the same claim in
other letters. `SEARCHER_BUCKET_POLICY.md` forbids a replica listing on
either public tab.

### Attack B — put a garment or an uncalibrated listing in Real

Uncalibrated raw 1.0 is 0.78 against a 0.80 gate. One table, footwear
only. `test_footwear_true_match_can_still_be_real` is the only Real path.

**Outcome.** Blocked for anything that is not designer footwear. That
half of the gate holds.

### Attack C — make a capability lie

`GET /v1/capabilities` on the live process (OpenCV installed, no
`embedding.pt`):

| Lane | available | lie? |
|---|---|---|
| `DENSE_FEATURES` | false, “No local embedding weights” | no |
| `LOCAL_CORRESPONDENCE` | **true**, ORB note | no |
| `OCR` | true, tesseract | matches the process that later SIGSEGV-spawns |

**Outcome.** No capability lie on this host.

### Attack D — default campaign coverage of 24 sources

Live campaign coverage after terminal: **24** source ids. Fifteen members
of `DEFAULT_ORDER` that used to be unnamed are now `sources_blocked` with
a reason.

**Outcome.** The product-level claim now holds. Round 5 Attack D is
closed.

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

The terminal report and scorecard still bind earlier SHAs and quote
rounds 1–4; they are not a self-grade of `72cc839`. Their own status
line is **NOT_READY**, which this pass independently agrees with.

---

## STATUS

NOT_READY.

No critical §38.2 score is ≥ 90. User-visible proof is 89. Behaviour 15
is not met. Replica language still reached Real. Known-item photographs
do not retrieve the listing. A live campaign now accounts for 24 sources.
`ontology_for(None)` is no longer footwear. `./scripts/flagship_acceptance.py --help`
exits 0.

## CLAIMS

1. Named replica strings (`replıca`, `not 100% authentic`, `un-authorized`,
   `un_authorized`, `not-authentic`) detected and cannot publish Real:
   **HOLD**.
2. Detector closed against novel obfuscations of the same claim: **FAIL**
   (18 Real leaks, including `isn't 100% authentic` and en-dash / Greek iota).
3. §32.9 eleven sabotages exist and are killed: **HOLD**. Bible item 12
   (`expose hidden benchmark answer`) is absent.
4. §32.1 measured; only matching meets 90/80: **HOLD** on receipt
   `7a3f314` (not remeasured at `72cc839`).
5. Budget exhaustion inside one source no longer drops later sources, both
   engines: **HOLD** (standalone + isolated unit). The one-process floor
   assertion is over-specified for the Bounded engine.
6. A campaign accounts for all 24 known sources: **HOLD** (live
   `515e5362`, 1 completed + 23 blocked).
7. Benchmark receipt names its scorer; separation on both bases: **HOLD**.
   Committed 0.810816 / +0.690816 does not reproduce (0.804228 / +0.684228
   and −0.105772).
8. `ontology_for(None)` is no longer footwear: **HOLD**.
9. `./scripts/flagship_acceptance.py --help` exits 0: **HOLD**.
10. Real only for designer footwear, honestly documented: **HOLD**.
11. Known-item photographs retrieve `8001001141404`: **FAIL**.
12. §40 behaviour 15: **FAIL** (Real=0 on committed receipts and on this
    host’s live campaign).
13. `source_limit=8` vs 9 planned: **HOLD** as a defect (still true).

## EVIDENCE

Commands that would fail if the supporting sentence were false:

- `python -m pytest -q --tb=line` → 16 failed, 585 passed, 3 skipped, 1
  deselected, 26 errors in 559.28s
- `python -m pytest tests/mutation -q -s` → 11 passed, 11 KILLED
- `python -m benchmark --all` → recall@1 0.914286, scorer ahash_colour,
  both separation keys present, false Real 0
- `python /tmp/searcher-r6-evidence/verify_claims.py` → 0 FAIL
- `python /tmp/searcher-r6-evidence/attacks.py` → 49 MISS / 17 CAUGHT
- `python /tmp/searcher-r6-evidence/real_publish.py` → 18 Real leaks;
  named family publishes replica
- `python /tmp/searcher-r6-evidence/both_engines_standalone.py` → both
  engines `missing=[]`
- live POST of `8001001141404_{1,2,3}.jpg` → search `515e5362`, 24
  named sources, target absent, walk note present, Real=[]
- `curl -sS -I https://shop.kind.co.jp/products/8006002318626` → 200
- `curl -sS -I https://shop.kind.co.jp/products/8001001141404` → 200
- `curl -sS -o /dev/null -w '%{http_code} %{size_download}' https://joshuahickscorp.github.io/searcher/` → 200 11322
- `./scripts/flagship_acceptance.py --help` → exit 0
- `./scripts/scrub_public_tree.sh` → PASS: working tree is clean
- `python -m ruff check src tests benchmark` → All checks passed
- `python -m mypy src` → 269 files, no issues
- `python -m pytest tests/security/test_ssrf_matrix.py tests/security/test_api_security.py` → 29 passed

Machine-readable traces live under `/tmp/searcher-r6-evidence/` and
`/tmp/searcher-r6-grade/artifacts/grading-round6/` (not committed; this
pass may write only this file).

## CHANGES

This lane wrote only `docs/grading/ROUND_6.md`. `src/`, `tests/`,
`benchmark/`, and the rest of the tree were read via `git show` /
`git archive` and were not edited. `python -m benchmark --all` rewrote
the receipt inside the throwaway archive tree only.

## TESTS

See Floor commands. Mutation, replica, 24-source, ontology, budget
(isolated), and real-gate tests passed. The one-process floor suite did
not. Soak and abuse never started. A live API campaign on this host
finished `PARTIAL` with 6 Possibly Real cards.

## RISKS

- SIGSEGV on `subprocess` after tesseract / `searcher serve` (same class
  as rounds 2–5). Isolated re-run of the spawn-sensitive units is green.
- Replica homoglyph / separator / contraction coverage is an open list.
  This pass reached Real without using any string the unit tests already
  contain.
- `source_limit=8` with 9 answerable names makes `archive_org`
  `UNMEASURABLE` on a default live campaign. The item being searched for
  can sit in a source that is never opened.
- `kind` still reports `SEARCHED_MATCHES_FOUND` for a catalogue walk.
  The walk note is present; the enum is not.
- `benchmark --all` without weights overwrites the committed DINOv2
  receipt with ahash numbers. `test_docs_match_capabilities` then fails
  `0.914 == 0.771` against the dirty file.

## UNRESOLVED

- Nothing live reaches Real. §40.15 is not met.
- Known KIND photographs do not retrieve that listing.
- `isn't 100% authentic` / en-dash / Greek-iota replica language
  publishes Real.
- `source_limit=8` against 9 planned sources.
- Floor suite is not green in one process.
- DINOv2 0.771 not reproduced without torch + weights.
- Coverage floor receipt is measured at `7a3f314`, not this SHA.
- Bible §32.9 item 12 (expose hidden benchmark answer) has no test.
- Soak/abuse still fail to spawn the API process in a one-process suite.

## NEXT

Smallest path to a status other than `NOT_READY`:

1. Fold contractions (`isn't` / `ain't`), en-dash / slash separators, and
   remaining homoglyphs (Greek iota, small caps, soft hyphen) into
   `self_declared_replica` and the generated property test. Re-attack with
   strings that are not in the suite.
2. Set live `source_limit` to the answerable set (9), or stop planning the
   name that the budget cannot consume. Keep the 24-name coverage map.
3. Either retrieve `8001001141404` from its own photographs into a public
   tab, or stop claiming known-item recall. Stop calling a catalogue walk
   `SEARCHED_MATCHES_FOUND` without changing the enum.
4. Keep `python -m pytest -q` from sharing an interpreter with tesseract /
   `searcher serve` (isolated splits already pass).
5. Put one live designer-footwear item in Real, or drop §40.15 from the
   claim ceiling.

Until 1–4 are independently re-run and the critical scores are ≥ 90,
the terminal status stays `NOT_READY`.
