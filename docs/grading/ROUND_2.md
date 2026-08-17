# Round 2 independent regrade

Graded 2026-08-16 against Bible §38 / §39 at commit
`a7a5a98949f47f350109ca648680985a334e2aee`. This pass did not write `src/`,
`tests/`, `scripts/`, `web/`, `benchmark/`, or `pyproject.toml`. Commands below
were run in this worktree. Stored receipts and commit messages were treated as
claims, not evidence.

§39 terminal status: **NOT_READY**.

No critical §38.2 dimension reaches 90. User-visible proof is also below 90.
Nothing in a live campaign reached Real (§40 behaviour 15). Replica language
that is not in the thirteen-phrase list still publishes to Possibly Real.
`benchmark --all` without local DINOv2 weights does not reproduce the cited
0.771 / 70% figures.

---

## Round-2 scores

| Dimension | R1 | R2 | One-line justification |
|---|---:|---:|---|
| Plan fidelity | 58 | 70 | Discovery, COMPLETE, and capability honesty now match the plan; §40.15 still fails and the 21/24 flagship score is on a substituted item, with behaviour 21 hard-coded `met`. |
| Implementation completeness | 62 | 73 | Index expansion, routing, and publication run; Real remains unreachable (auth lower bound 0.40, missing label/logo/provenance) and three marketplaces stay unadmitted. |
| Real-runtime proof | 45 | 71 | Live campaign test passed (149.72s); independent KIND expansion and Willy search published ranked live links; soak/abuse still force `SEARCHER_LIVE_DISCOVERY=0`. |
| User-visible proof | 64 | 73 | Live results carry `listing_url`, reason codes, and compare; `_publish` will still emit Possibly Real with `listing_url: null` and no reason codes if a bare decision is inserted. |
| Retrieval quality | 38 | 64 | DINOv2 recall@1 0.771 / recall@5 1.0 reproduced; live known-item rank 1; shipped 0.86 still admits 70% of different-listing pairs. |
| Authenticity safety | 42 | 83 | All 13 previously leaking phrases now publish as `replica`, never Real; 30 extra seller phrasings still reach Possibly Real with perfect scores. |
| Security and privacy | 82 | 83 | SSRF, upload, deletion, and isolation tests passed; history scrub is still dirty; soak/abuse do not exercise live fetch. |
| Cost efficiency | 78 | 80 | Fixture warm-index cache-hit 1.0 reproduced; the cheap 2s path is gone — a live API-bounded campaign took 205s and stopped on budget. |
| Test quality | 60 | 76 | 395 + 1 live passed; replica/COMPLETE/capability/docs tests exist; mypy fails without torch; 3 of 9 corrected docs are unguarded; extra replica phrases untested. |
| Documentation | 55 | 77 | Nine files were corrected and a revert of a guarded sentence fails the test; the shortlist-cut language lives in a code comment; cited 0.771 is DINOv2-only. |

Critical floor is 90 (§38.2): plan fidelity, implementation completeness,
real-runtime proof, security/privacy, authenticity safety, test quality.
User-visible product wave also needs user-visible proof ≥ 90. None of those
cleared.

---

## Floor commands

| Command | Result |
|---|---|
| `./scripts/test_all.sh` | Fast suite **395 passed, 6 skipped, 1 deselected in 53.56s**. Live campaign **1 passed, 401 deselected in 149.72s**. Wrapper exit 1 was from `tee` to a not-yet-created log dir, not from pytest. Log: `artifacts/grading-round2/test_all.log`. |
| `uv run ruff check .` | `All checks passed!` |
| `uv run mypy src` | **Fails without the vision extra** (`src/searcher/bench/stage_latency.py:284: Class cannot subclass "Module" (has type "Any") [misc]`, exit 1). **Passes after `uv sync --extra vision`** (`Success: no issues found in 261 source files`). |
| `uv run python -m benchmark --all` | Runs. Without weights: recall@1 **0.914286**, scorer `searcher.cheap_visual.ahash_colour`. With `SEARCHER_EMBEDDING_WEIGHTS` pointing at the host DINOv2 file: recall@1 **0.771429**, MRR **0.866667**, false Real **0** — headline numbers match the stored receipt. Also rewrote two committed fixture PNGs (see defects). |
| `uv run python -m benchmark.threshold` | Without weights: shipped 0.86 held-out FPR **0.0**, verdict "holds". With DINOv2: shipped 0.86 held-out TPR **0.5**, FPR **0.7**, verdict **"chosen threshold does not hold on held-out data"** — matches the stored receipt. |
| `./scripts/scrub_public_tree.sh` | Exit **1**. History still has `$HOME` / home-path hits. Committed working-tree hits include `docs/audit/REDTEAM_COMPLETENESS.md`. This lane's logs under `artifacts/grading-round2/` added more home-path findings. |
| `git status --porcelain` | Allowed dirty paths under `docs/` and `artifacts/`. Unintended dirty: `fixtures/hard_negatives/artifacts/adjacent.png` and `true_match.png` (rewritten by `benchmark --all`). This lane could not restore them (`index.lock: Operation not permitted`; fixture writes denied). Supervising session should `git checkout --` those two files. |

Fast-suite timing claim of 52s is **53.56s** here. Live-campaign timing claim of
~130s is **149.72s** here.

---

## Claim checks

Each claim was run through something that would fail if it were false.

### 1. A replica can no longer reach Real; thirteen phrasings are regression tests

**Command.** `uv run python artifacts/grading-round2/attacks.py` plus
`uv run python -m pytest -q tests/unit/test_replica_phrases.py`.

**Result.** `LEAKED` in `tests/unit/test_replica_phrases.py` has **13** strings.
`pytest` parametrizes each. The attack routed every one of those 13 through
`route_candidate` + `published_public_bucket` with perfect match/authenticity
scores:

- detected: true
- routed public: `hidden`
- published: `replica`
- **reached Real: []**

A replica-family adapter (`yupoo`) with a stored Real decision also published as
`replica`. Ordinary listings (faux fur, fake leather, Authentic Prada) were not
flagged.

**Verdict.** The stated claim holds. See claim 6 residual: other phrasings still
reach Possibly Real.

### 2. Discovery expands listing indexes (18 products / 60 images, not one imageless collection URL)

**Command.** `uv run python artifacts/listing-expansion/run_kind_live.py`

**Result.**

```text
candidates 24
product_urls 24
with_images 24
images (candidate_images rows) 140
index_canonical_urls []
members_found 225, taken 24, dropped 201 (per_index_cap)
first URL https://shop.kind.co.jp/products/8001001141404 (5 images)
```

The before-state in `artifacts/listing-expansion/BEFORE.md` (one imageless
`products.json` collection URL) is gone on this path. The exact **18 / 60**
counts did not reproduce: the default per-index cap is 24, and this shop feed
now has 225 members. An API-bounded campaign (claim 3) produced 9 product URLs
and 53 images, still none of them an index URL.

**Verdict.** Expansion works. The 18/60 figure is a single earlier run, not an
invariant.

### 3. A live search publishes 5 Possibly Real, true listing first, working link

**Command.** `uv run python artifacts/grading-round2/live_willy_search.py`
(same sources and `max_work=8` as `run_api_campaign`), then `curl -sI` on each
published URL, then `list_public_results` on the stored campaign.

**Result.**

| Field | Observed |
|---|---|
| terminal | `PARTIAL` / `budget exhausted` in 205.01s |
| Possibly Real | **4** (not 5) |
| Real | 0 |
| true listing | `https://shop.kind.co.jp/products/8001001141404` at **rank 1** |
| `listing_url` | present on all 4 |
| HTTP | **200** on all 4 |
| tab_reason | includes `Reason codes: possibly-real-gate.` |
| images_compared | 5, 5, 1, 1 (populated, not `[]`) |
| auth lower bound | 0.40 on every published row |

**Verdict.** Rank-1 true listing and working links hold. The count of 5 does
not; this run published 4. Stored `artifacts/realmatch/results.json` had 3.
The number is run-dependent.

### 4. §40 flagship scores 21 of 24, up from 12

**Commands.** Read stored receipts; independently evaluate the Willy campaign
above with `scripts/flagship_acceptance.py:evaluate`.

**Stored.**

- `artifacts/searcher-flagship-acceptance.receipt.json` — **Dior §40 input**:
  met 13, not met 3, not evaluable 8. Real=0, Possibly Real=0.
- `artifacts/searcher-flagship-matched.receipt.json` — **Willy Chavarria**,
  not the Bible item: met 21, not met 1, not evaluable 2. Real=0, Possibly Real=5.

**Independent.** Same evaluator on this pass's Willy campaign:
**met 21, not met 1, not evaluable 2**. The single `not met` is behaviour 15
(Real). Behaviours 2 and 5 are `not evaluable` (crops and hypotheses are not
in the API). Behaviour 21 is hard-coded `met` in the script ("covered by
crash-resume tests") and was not demonstrated on this campaign.

**Verdict.** 21/24 reproduces on a Willy campaign under their evaluator. It is
not the Bible §40 Dior scenario. Dior remains 13/24. Behaviour 21 is not
earned by the campaign under test.

### 5. COMPLETE now requires that source work actually ran

**Command.** Attack `complete_without_fetch` in
`artifacts/grading-round2/attacks.py`. Also
`tests/integration/test_terminal_requires_work.py` (part of the 395).

**Result.**

| Case | State | Reason |
|---|---|---|
| empty campaign | `BLOCKED` | no usable query was compiled |
| query compiled, no source work | `BLOCKED` | no source work was planned |
| source marked completed, `pages_fetched=0`, no candidates | `BLOCKED` | nothing was fetched |
| `forced=COMPLETE` override | `COMPLETE` | internal override only |

**Verdict.** Holds on the public path. The forced override is not a user path.

### 6. A capability reports available only after a probe that really loads and runs

**Command.** Attack `capability_lie`; then, after installing torch and pointing
at a real weights file:

```text
SEARCHER_EMBEDDING_WEIGHTS=.../embedding.pt
embedding_capability(probe=True)
```

**Result.**

| Case | available | notes |
|---|---|---|
| dummy file, no probe | false | `unknown` … `not probed` |
| dummy file, `probe=True` (no torch) | false | torch not importable, probe could not run |
| zero-byte file | false | treated as missing |
| missing path | false | no weights |
| `GET /v1/capabilities` path (`probe_capabilities`) | DENSE_FEATURES false | **does not call `probe=True`** |
| dummy + internal `record_probe_result(True)` | true | cache poison; not a public API |
| real `embedding.pt` + torch + `probe=True` | **true** | `probe call succeeded; no download performed` |

`NEXT_VIEW` is hard-coded `available=True` without a load/run probe.

**Verdict.** DENSE_FEATURES does not claim available from file existence.
Availability after a real forward pass was confirmed once torch and weights
were present. The HTTP capabilities endpoint never probes.

### 7. Nine documents were corrected; a test fails when docs and code disagree

**Command.** `uv run python artifacts/grading-round2/verify_docs_and_threshold.py`
and `tests/unit/test_docs_match_capabilities.py` (31 tests in the targeted
re-run, including this file).

**Result.** Commit `efdd124` touched nine documents:

`ARCHITECTURE.md`, `CLAIMS.md`, `LIMITATIONS.md`, `README.md`,
`docs/OPERATING.md`, `docs/architecture/API.md`,
`docs/architecture/EMBEDDINGS.md`,
`docs/architecture/MATCHING_AND_AUTHENTICITY.md`, `web/index.html`.

All nine exist. None of the nine forbidden phrases remain. Required phrases
(DINOv2, `recall@1 0.771`, `SEARCHER_LIVE_DISCOVERY`, …) are present in the
guarded set. A simulated revert of
`discovery is not wired into that process` into `ARCHITECTURE.md` would fail
the test.

The test guards **six** of the nine files. `README.md`, `docs/OPERATING.md`,
and `docs/architecture/MATCHING_AND_AUTHENTICITY.md` are unguarded.

**Verdict.** Nine documents were corrected. The disagreement test is real and
narrower than the claim.

### 8. Pair threshold is a shortlist cut, not an identity gate; 0.86 admits 70% of different-listing pairs

**Command.** `uv run python -m benchmark.threshold` with DINOv2 weights.
Read `src/searcher/core/embedding_gateway.py` (`OPERATING_THRESHOLD` comment)
and public docs.

**Result.** DINOv2 regeneration:

```text
scorer: facebookresearch.dinov2.vits14
shipped 0.86 on held out: tpr 0.5, fpr 0.7
verdict: chosen threshold does not hold on held-out data
```

That is exactly the stored receipt. The 70% figure is reproduced.

The phrase "shortlist cut" / "not a validated identity gate" appears in
`src/searcher/core/embedding_gateway.py`. It does **not** appear in
`CLAIMS.md`, `LIMITATIONS.md`, `docs/architecture/EMBEDDINGS.md`,
`SEARCHER_BUCKET_POLICY.md`, or `README.md` (those mention 0.86 or the
retrieval figures only).

Without weights the same command reports shipped FPR **0.0** on the cheap
scorer — the 70% number is DINOv2-specific.

**Verdict.** The measurement holds. The public-doc half of the claim is thin.

### 9. Fast suite 52s; live campaign ~130s

**Command.** Timed `./scripts/test_all.sh`.

**Result.** 53.56s and 149.72s. Same order of magnitude, not the quoted
numbers.

---

## Four attacks

Recorded in `artifacts/grading-round2/attacks.json`.

### Attack A — publish a replica to Real

Attempted with the 13 regression phrases plus 35 extra seller phrasings, all
given perfect match and authenticity scores under `matching-1`.

- **13/13 regression phrases:** published `replica`, never Real, never Possibly
  Real.
- **Replica-family source** with a stored Real decision: published `replica`.
- **30 extra phrases published Possibly Real**, including `super copy`,
  `isn't authentic`, `ain't genuine`, `replika`, `réplique`, `imitation`,
  `1/1 pair`, zero-width `re\u200bplica`, and `this isn't the authentic pair`.
- Five extras were caught (`AAA+`, `aaa quality`, `this is a rep`,
  `unauthorised replica`, `not original item`).

**Outcome.** Failed to reach Real. Succeeded in putting undeclared replica
language on the Possibly Real tab, which `SEARCHER_BUCKET_POLICY.md` forbids
("A replica listing can never be ranked Real or Possibly Real").

### Attack B — reach COMPLETE without fetching

Empty campaign, compiled-query/no-source, and
`sources_completed` + `pages_fetched=0` all returned `BLOCKED` with a named
reason. Only `forced=COMPLETE` produced COMPLETE.

**Outcome.** Blocked on the public path.

### Attack C — make a capability lie

A dummy or empty weights file never produced `available=True` through
`embedding_capability` or `probe_capabilities`. Unprobed files report
`unknown`, not available. A real weights file plus `probe=True` reported
available only after a forward pass.

**Outcome.** Blocked for DENSE_FEATURES. `NEXT_VIEW` is advertised available
without a probe (different capability).

### Attack D — publish a result without a reason or a link

Inserted a Possibly Real decision with empty `canonical_url` and empty
`reason_codes`, then called `CampaignOrchestrator._publish`.
`list_public_results` returned one Possibly Real row with
`listing_url: null` and tab_reason
"The item may match, but important evidence is missing or conflicting."
(no reason codes). A `javascript:alert(1)` URL published with
`listing_url: null` (stripped by `safe_http_url`) but still on the public
list.

The honest `route_candidate` path always attaches a reason code and a
real `https` URL, and those survive projection.

**Outcome.** Leak on the publish/projection path. Not the default router.

---

## Receipt comparisons

Canonical cited receipts were restored after comparison so `CLAIMS.md` /
the docs test still match the DINOv2 figures. Copies live under
`artifacts/grading-round2/receipts-before/` and
`artifacts/grading-round2/receipts-after/`.

### `searcher-public-benchmark.receipt.json`

| | Stored | Regen, no weights | Regen, DINOv2 |
|---|---|---|---|
| SHA-256 | `2c6701abf8f8…` | `40f8cd943973…` | `87ea7f9780bb…` (identity/time differ) |
| scorer | `facebookresearch.dinov2.vits14` | `searcher.cheap_visual.ahash_colour` | `facebookresearch.dinov2.vits14` |
| n | 35 | 35 | 35 |
| recall@1 | 0.771429 | **0.914286** | **0.771429** |
| recall@5 | 1.0 | 1.0 | 1.0 |
| MRR | 0.866667 | 0.940476 | **0.866667** |
| false Real | 0 | 0 | 0 |

Headline retrieval numbers reproduce if and only if local DINOv2 weights
load. The floor command as written, on a clean tree without
`SEARCHER_EMBEDDING_WEIGHTS`, overwrites the cited receipt with 0.914 and
would fail `test_docs_match_capabilities.py`.

### `searcher-threshold.receipt.json`

| | Stored | Regen, no weights | Regen, DINOv2 |
|---|---|---|---|
| scorer | dinov2 | cheap visual | dinov2 |
| shipped 0.86 held-out TPR | 0.5 | 0.3 | **0.5** |
| shipped 0.86 held-out FPR | 0.7 | **0.0** | **0.7** |
| chosen | 0.95 / tpr 0.3 / fpr 0.0 | 0.83 / tpr 0.4 / fpr 0.0 | **0.95 / tpr 0.3 / fpr 0.0** |
| verdict | does not hold | **holds** | **does not hold** |

The 70% different-listing admission is reproduced on DINOv2.

### `searcher-performance.receipt.json`

| | Stored | Regen |
|---|---|---|
| cold campaign_wall_ms | 49.069 | 53.526 |
| warm campaign_wall_ms | 29.266 | 32.696 |
| warm cache_hit_rate | 1.0 | **1.0** |
| duplicate_work_avoided | 1.0 | **1.0** |
| cold candidates / results | 5 / 5 | 5 / 5 |

Shape holds. Timings moved a few milliseconds on this host.

---

## What would raise each score below 90

**Plan fidelity (70).** Run the Bible §40 Dior input to a campaign that
satisfies behaviour 15 (a Real result earned by evidence, not a lowered
gate). Stop hard-coding behaviour 21 as `met`. Emit the §39 files under
the names the Bible lists, or amend the Bible.

**Implementation completeness (73).** Same Real result. Add a garment
authenticity profile so a shirt is not judged with an empty profile and a
0.40 authenticity floor. Either admit Grailed / Vestiaire / Depop under a
real policy or keep them disabled (already honest) and stop counting them
as missing coverage.

**Real-runtime proof (71).** Flip soak/abuse to `SEARCHER_LIVE_DISCOVERY=1`
and stop asserting `BLOCKED` as the only honest soak outcome. Re-run the
21-case adversarial-recall receipt against the expanded discovery path.

**User-visible proof (73).** Make `_publish` refuse a public bucket when
`safe_http_url(canonical_url)` is missing or `reason_codes` is empty.
Expose crops and hypotheses so behaviours 2 and 5 are evaluable.

**Retrieval quality (64).** A pair threshold that holds on held-out data
at the 5% FPR ceiling, on a labelled set larger than 10+10. Report
Real-tab precision once anything is in Real.

**Authenticity safety (83).** Treat `super copy`, contractions (`isn't
authentic`), transliterations (`replika` / `réplique`), `1/1`, and
zero-width inserts as replica language; add them to the regression list.
Field-calibrate authenticity so the interval is not stuck at 0.40.

**Security and privacy (83).** Rewrite history so
`./scripts/scrub_public_tree.sh` is clean with
`SEARCHER_SCRUB_FAIL_ON_HISTORY=1`. Run soak/abuse against live discovery.
Authentication if this process is ever shared beyond a single operator.

**Cost efficiency (80).** A live cost ledger with cache-hit rate and a
first-published-result time that is not "budget exhausted after 200s".

**Test quality (76).** Make `uv run mypy src` pass on the default extra
(the `Module` subclass error). Guard the three unguarded documents. Add
tests for extra replica slang and for "no public row without a link and a
reason". Stop asserting soak `BLOCKED` while claiming live discovery is
the default.

**Documentation (77).** Put "shortlist cut, not an identity gate" and the
70% held-out FPR in `CLAIMS.md` / `LIMITATIONS.md` next to 0.86. Cite the
scorer identity next to 0.771 so a no-weights `benchmark --all` cannot
silently retitle the receipt. Add the missing §39 filenames.

---

## §39 terminal status

**NOT_READY.**

Required named deliverables that are absent under the Bible names (some
exist under other paths; that is not the list in §39):

- `SEARCHER_SOURCE_AUTHORITY.md`, `SEARCHER_REUSE_LEDGER.json`,
  `SEARCHER_ARCHITECTURE.md`, `SEARCHER_DATA_MODEL.md`,
  `SEARCHER_UX_SPEC.md`, `SEARCHER_PERFORMANCE_BASELINE.md`,
  `SEARCHER_RELEASE_READINESS.md`, `SEARCHER_TERMINAL_REPORT.md`
- `artifacts/searcher-clean-clone.receipt.json`,
  `artifacts/searcher-security.receipt.json`,
  `artifacts/searcher-terminal.receipt.json`

Present under close names: `ARCHITECTURE.md`, `SOURCE_POLICY.md`,
`SEARCHER_AUTHENTICITY_POLICY.md`, `SEARCHER_BUCKET_POLICY.md`,
`SECURITY.md`, `PRIVACY.md`, `LIMITATIONS.md`,
`docs/SEARCHER_BENCHMARK_METHOD.md`,
`docs/SEARCHER_PUBLIC_BENCHMARK_REPORT.md`,
`SEARCHER_FINAL_SCORECARD.md`, plus several audit receipts under
`artifacts/audit/`.

### Smallest set that would clear NOT_READY

In order, because §38.2 does not average:

1. **Close residual replica language** so a listing that says `super copy`
   / `isn't authentic` cannot land on Possibly Real, and lock it with
   tests. (Authenticity safety → 90.)
2. **Earn one Real** on an authorized item that actually has the views the
   gate demands — or change the garment profile so a shirt can pass
   honestly. Without behaviour 15, plan fidelity and implementation
   completeness cannot reach 90 against this Bible.
3. **Hermetic mypy + publish-requires-link + unguarded-doc tests + soak
   with live discovery.** (Test quality and real-runtime proof.)
4. **History rewrite** so the public-tree scrub is clean.
5. **Write the missing §39 terminal files** from evidence that already
   exists.

Item 2 is the hard blocker. This tree is willing to say "nothing reaches
Real" and that is currently true. The Bible still requires high-evidence
candidates in Real for the flagship. Until that happens, or the Bible is
amended, the terminal status stays NOT_READY.

---

## Defects this pass opened (not in the admitted list)

- `_publish` will place a Possibly Real row with no link and no reason
  codes.
- Thirty extra replica phrasings, including ordinary English (`super
  copy`, `isn't authentic`), reach Possibly Real.
- `uv run python -m benchmark --all` without weights overwrites the cited
  public receipt and would fail the docs test.
- The same command rewrote committed
  `fixtures/hard_negatives/artifacts/adjacent.png` and `true_match.png`.
- Soak and abuse still set `SEARCHER_LIVE_DISCOVERY=0` and assert
  `BLOCKED`.
- Flagship behaviour 21 is unconditionally `met`.
- `GET /v1/capabilities` never probes DENSE_FEATURES.
- Default-extra mypy fails; vision-extra mypy passes.

Admitted weaknesses confirmed, not rediscovered: nothing reaches Real;
Grailed / Vestiaire / Depop stay out; the backbone bake-off that chose
DINOv2 is not in this tree. The DINOv2 **receipts** do reproduce when the
operator's weights file is pointed at.

---

## Evidence index

| Path | What |
|---|---|
| `artifacts/grading-round2/attacks.json` | Four attacks |
| `artifacts/grading-round2/docs-threshold.json` | Nine-doc and shortlist-cut scan |
| `artifacts/listing-expansion/live-kind.json` | Live KIND expansion |
| `artifacts/grading-round2/live-willy.json` | Independent live search |
| `artifacts/grading-round2/live-willy-projected.json` | Projected reasons/links |
| `artifacts/grading-round2/live-willy-flagship.json` | Independent 21/24 evaluation |
| `artifacts/grading-round2/receipts-before/` | Snapshots of cited receipts |
| `artifacts/grading-round2/receipts-after/` | Cheap-scorer regenerations |
| `artifacts/grading-round2/receipts-after/dinov2/` | DINOv2 regenerations |
| `artifacts/grading-round2/test_all.log` | Timed full suite |
| `artifacts/grading-round2/benchmark-all.log` | No-weights `--all` |
| `artifacts/grading-round2/benchmark-all-dinov2.log` | DINOv2 `--all` |
| `artifacts/grading-round2/benchmark-threshold.log` | No-weights threshold |
| `artifacts/grading-round2/benchmark-threshold-dinov2.log` | DINOv2 threshold |
| `artifacts/grading-round2/scrub.full.txt` | Scrub output |
