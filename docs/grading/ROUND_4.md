# Round 4 independent regrade

Graded 2026-08-17 against Bible §38 / §39 at commit
`31e6004c76e1d845447e0993a5ce68948f311265`. This pass did not write `src/`,
`tests/`, `scripts/`, `web/`, `benchmark/`, `fixtures/`, or `pyproject.toml`.
Commands below were run in this worktree. Commit messages, `SEARCHER_FINAL_SCORECARD.md`,
and `artifacts/searcher-speed.receipt.json` were treated as claims, not evidence.

§39 terminal status: **NOT_READY**.

No critical §38.2 dimension reaches 90. User-visible proof is 87. Nothing in a
live campaign reached Real (§40 behaviour 15). `r3pl1ca` still publishes as
Possibly Real. The default API campaign plans `rebag` and then marks it
`SOURCE_UNAVAILABLE` after a 20s source deadline. `./scripts/test_all.sh` in one
process ended 14 failed / 26 errors with SIGSEGV on child spawn.

---

## Round-4 scores

Round 3 in the contract is the independent pass recorded at `6435d24` (the
numbers live in `artifacts/grading-round3/scores.json` and `docs/grading/ROUND_2.md`).
This pass scores `31e6004`.

| Dimension | R3 | **This pass** | One-line justification |
|---|---:|---:|---|
| Plan fidelity | 78 | **82** | Registry-derived uncredentialed plan, Rebag spec, garment views, label-hash, replica property tests, reason+link, and host overlap match the recent plan; default campaigns still expire `rebag` at 20s; §40.15 and named §39 files still fail. |
| Implementation completeness | 80 | **84** | Four garment paths no longer ask for a sole; compare strips shoe parts; completeness 0.80; dedicated `shop.rebag.com` works; ORB runs; publication gates hold. `ontology_for(None)` and the pipeline still default to footwear; `LOCAL_CORRESPONDENCE` reports unavailable while ORB answers. |
| Real-runtime proof | 77 | **76** | Independent live Rebag (135s) and Pages+tunnel search both ran. Floor suite 14 failed / 26 errors / SIGSEGV in 756s; `live_campaign` timed out at 180s; soak/abuse never started (`API process exited -11`). |
| User-visible proof | 84 | **87** | Pages 200; tunnel health 200; CORS from the Pages origin; a Willy snapshot search published 1 Possibly Real with an `https` link (HTTP 200) and reason codes. Reason-less publish is closed. Real is still empty. |
| Retrieval quality | 73 | **72** | `benchmark --all` without weights: recall@1 **0.914** on `searcher.cheap_visual.ahash_colour`, not the cited 0.771. Live published `8001001141442`, not the snapshot's own `8001001141404`. Torch was absent. |
| Authenticity safety | 88 | **89** | Unequal label hashes are not `STRONG_COUNTERFEIT`. Homoglyph / ZWSP / spacing replica text cannot publish Real. Property tests exist. `r3pl1ca` still reaches Possibly Real. |
| Security and privacy | 83 | **82** | SSRF/upload tests are inside the 493 that passed before spawn death. Abuse/soak did not run. `scrub_public_tree.sh` FAIL (1981 working-tree findings; history still dirty). Tunnel is unauthenticated, as documented. |
| Cost efficiency | 81 | **83** | Independent 3-run worker-entry median **107146ms**; every planned source starts together (~125ms). Stored 95705ms was not reproduced. Dedicated Rebag 135s. Default Rebag still burns 20s to `SOURCE_UNAVAILABLE`. |
| Test quality | 85 | **83** | Property tests cover replica / URL / reason; correspondence and label-hash tests exist. Floor suite no longer completes in one process. Isolated re-run of the spawn-sensitive units: 95 passed. |
| Documentation | 80 | **80** | Alias docs exist; the scorecard still says round 2 has not been run. Six of the §39 named files and five of the seven named receipts are missing. |

Critical floor is 90 (§38.2): plan fidelity, implementation completeness,
real-runtime proof, security/privacy, authenticity safety, test quality.
A user-visible product wave also needs user-visible proof ≥ 90. None of
those cleared.

Anything below 90, what would raise it:

- **Plan fidelity (82):** a default API campaign must actually retrieve
  `shop.rebag.com` listings (not `SOURCE_UNAVAILABLE` at 20s), and the
  named §39 files must exist.
- **Implementation completeness (84):** `ontology_for(None)` / pipeline
  default must stop applying footwear; `GET /v1/capabilities` must report
  `LOCAL_CORRESPONDENCE` available when ORB runs.
- **Real-runtime proof (76):** `./scripts/test_all.sh` green without
  SIGSEGV; `pytest -m live_campaign` pass; soak/abuse start.
- **User-visible proof (87):** at least one Real card on a live campaign;
  the first-run shoe fixture must not be the only demo path.
- **Retrieval quality (72):** reproduce DINOv2 recall@1 0.771 on this host;
  live rank-1 must be the snapshot's own listing.
- **Authenticity safety (89):** `r3pl1ca` (and the same leet family) must
  not publish Possibly Real.
- **Security and privacy (82):** scrub working-tree 0; abuse/soak actually
  exercise a live API process.
- **Cost efficiency (83):** median of three on this host in the 95s
  neighbourhood *and* Rebag must not spend a full 20s dying.
- **Test quality (83):** floor suite green in one process; a generated
  `r3pl1ca`-class case in the property test.
- **Documentation (80):** the §39 filenames, a terminal report, and a
  scorecard that is not still waiting for round 2.

---

## Floor commands

| Command | Result |
|---|---|
| `./scripts/test_all.sh` | Fast suite **14 failed, 493 passed, 6 skipped, 1 deselected, 26 errors in 756.35s**. Multiple `Fatal Python error: Segmentation fault` in `run_tesseract` / child spawn. Wrapper recorded as the floor run. Log: `artifacts/grading-round4/test_all.log`. The second invocation (`-m live_campaign`) did not contribute a passing line in that log. |
| Isolated `pytest -m live_campaign` | **1 failed** in 180.78s (`test_live_orchestrator_campaign` timeout during live verify / host rate sleep). Log: `artifacts/grading-round4/live_campaign.log`. |
| Isolated spawn-sensitive units | **95 passed in 1.89s** (`test_serve_shared`, `test_first_run`, `test_probe_and_import`, replica / publication / correspondence / label-hash / publish-link / gap-views). Log: `artifacts/grading-round4/targeted_unit.log`. |
| `uv run ruff check .` | `All checks passed!` after unused imports in this lane's scripts were removed. `artifacts/grading-round4/ruff.log`. |
| `uv run mypy src` | **Passes without torch installed.** `Success: no issues found in 269 source files`. `importlib.util.find_spec("torch")` was `False`. `artifacts/grading-round4/mypy.log`. |
| `uv run python -m benchmark --all` | Runs. Without weights: recall@1 **0.914286**, scorer `searcher.cheap_visual.ahash_colour`, false Real **0**. Overwrites the committed receipt and two fixture PNGs; those were restored from `git archive HEAD` so the tree is not left dirty. Log: `artifacts/grading-round4/benchmark-all.log`. |
| `./scripts/scrub_public_tree.sh` | Exit **1**. `FAIL: 1981 working-tree finding(s)`. History still has `$HOME` / home-path hits. This lane's files under `artifacts/grading-round4/` added volume. |
| `git status --porcelain` | Allowed dirty paths under `docs/` and `artifacts/` only. Fixture PNGs and receipts rewritten by the benchmark were restored. |

The first invocation of `test_all.sh` (before `migrations/` was materialized
from git) was 15 failed / 96 errors, almost all `cannot locate migrations/`.
That is a sparse-checkout artifact, not a product bug. After `git archive HEAD
migrations` the numbers above are the ones that count.

---

## Claim checks

Each claim was run through something that would fail if it were false.

### 1. The alpha is reachable by a stranger: GitHub Pages + Cloudflare tunnel returns real results with working links

**Command.** Fetch `https://joshuahickscorp.github.io/searcher/` (status 200,
11758 bytes, contains `Searcher`). Start `searcher serve` + `cloudflared
tunnel --url`. This host's `getaddrinfo` cannot resolve `*.trycloudflare.com`
(Errno 8); `dig @1.1.1.1` returns Cloudflare anycast A records. The probe
connected with SNI to that IP. POST `/v1/searches` with
`Origin: https://joshuahickscorp.github.io` and a Willy snapshot. Poll
results. HEAD the published `listing_url`.

Script: `artifacts/grading-round4/pages_tunnel.py`.
Reports: `pages_tunnel.willy.json` (fair image),
`pages_tunnel.trainer_a.json` (first-run shoe fixture).

**Result, Willy snapshot** (`fixtures/user_snapshots/8001001141404_snapshot.jpg`,
text `Willy Chavarria`, tag `garment`):

| Field | Observed |
|---|---|
| Pages | HTTP **200**, interface present |
| Tunnel health | HTTP **200**, `status=ok` |
| CORS `Access-Control-Allow-Origin` | `https://joshuahickscorp.github.io` |
| Create | **201**, `search_id` issued |
| Terminal | `PARTIAL` |
| Possibly Real | **1** |
| Real | **0** |
| Card | `https://shop.kind.co.jp/products/8001001141442` |
| Link | **HTTP 200** |
| Reason | `possibly-real-gate` |

**Result, first-run shoe fixture** (`fixtures/images/trainer_a.png` + the same
Willy text): 8 hidden, 0 public. Every judged row was `INSUFFICIENT_MATCH`
(item lower ~0.27–0.32). Kind still found 24 product URLs.

**Verdict.** The stranger path **holds** when the upload is a photograph of
the garment. It does **not** hold for the first-run shoe PNG. Real is empty
either way. This host cannot resolve the tunnel hostname through the system
resolver; a browser using 1.1.1.1 / 8.8.8.8 can (A records exist).

### 2. Reach is self-sufficient: no API key, plan from the registry, live campaign returns shop.rebag.com

**Command.** `uv run python artifacts/grading-round4/verify_claims.py`
(`check_reach_self_sufficient`) and
`uv run python artifacts/grading-round4/live_rebag.py`.

**Uncredentialed plan** (derived from `ADAPTER_REGISTRY` ∩ `DEFAULT_ORDER`,
dropping `requires_operator_credential`):

```text
searx, wikimedia, marginalia, the_realreal, rebag, komehyo, kind,
byronesque, heroine, archive_org
```

`ebay` and `etsy` are out. `rebag` is in. No planned adapter requires an
operator credential. The iterator is still `DEFAULT_ORDER`, not
`ADAPTER_REGISTRY.keys()`; every currently enabled uncredentialed adapter
happens to sit in that order.

**Dedicated live campaign** (`source_names=["rebag"]`, 135237ms):

| Field | Observed |
|---|---|
| `requires_operator_credential` | **False** |
| Vendor / handle picked from `https://shop.rebag.com/products.json` | Celine / `handbag-celine-boston-bag-triomphe-coated-canvas-small-144114525` |
| Coverage | `rebag=SEARCHED_MATCHES_FOUND` |
| Catalog URLs | `https://shop.rebag.com/products.json?limit=250&page=1` |
| Listing URLs | 12+ `https://shop.rebag.com/products/...` |
| `kind` in coverage | absent |

**Default API campaign** (Pages+tunnel and all three worker-entry latency
runs): `rebag` is planned, starts at ~125ms with the other hosts, runs
~20050ms, and is recorded `SOURCE_UNAVAILABLE`. No `shop.rebag.com`
listing is published. The 20s source deadline is the observed ceiling.

**"No API key or agreement anywhere"** is false if read literally:
`EbayApiAdapter` / `EtsyApiAdapter` still exist and require operator
secrets; they are excluded from the live plan. Marginalia uses the
published `public` key.

**Verdict.** Self-sufficient dedicated reach **holds**. Default-campaign
reach to a second shop **does not**. Registry-derived planning **holds**
for the adapters that are both enabled and in `DEFAULT_ORDER`.

### 3. Campaign wall time roughly halved, 199474ms to 95705ms median of three

**Command.** `uv run python -m searcher.bench.stage_latency --phase after
--runs 3 --worker-entry --output artifacts/grading-round4/stage_latency.after.json`

The stored `artifacts/searcher-speed.receipt.json` (`before.median_wall_ms
= 199474.107`, `after.median_wall_ms = 95704.578`) was **not** accepted.

**Independent after (this host, this commit):**

| Run | wall_ms | terminal |
|---:|---:|---|
| 1 | 107145.848 | PARTIAL |
| 2 | 118841.192 | PARTIAL |
| 3 | 87622.849 | PARTIAL |
| **median** | **107145.848** | |

All planned sources start together (`started_ms` 123–145). That is the
overlap. The stored 95705ms median was **not** reproduced (this host is
~12s slower). The stored 199474ms before figure was **not** re-measured
on old code; a comparison against it is not an independent proof.

**Verdict.** Current median is **107s**, not 95.7s. Host-overlap is
independently visible. "Roughly halved from 199474" is a ledger
comparison this pass did not rerun.

### 4. Correspondence ran on a fallback that cannot distinguish two objects until opencv; ORB now separates at TPR 1.000 / FPR 0.000 on fixtures/user_snapshots

**Command.** `uv run python artifacts/grading-round4/orb_measure.py` with
the `correspondence` extra installed. Then the same pairs with
`features.opencv_available = lambda: False`
(`fallback_measure.py`).

**ORB (opencv 5.0.0, method `orb`):**

| | same object | other object |
|---|---:|---:|
| inliers | 33,14,17,69,16,28,50,37,86,57 | 4,0,0,0,3,0,0,0,0,7 |
| median | 35 | 0 |
| min / max | 14 / 86 | 0 / 7 |
| TPR @ 10 | **1.000** | |
| FPR @ 10 | **0.000** | |

**BRIEF fallback (opencv hidden):**

| | same | other |
|---|---:|---:|
| median | 6.5 | 5.5 |
| min / max | 5 / 10 | 5 / 12 |
| TPR @ 10 | 0.100 | |
| FPR @ 10 | 0.100 | |
| ranges overlap | **yes** | |

`fixtures/user_snapshots/MANIFEST.json` states the snapshots are warps of
the listing pixels, so TPR 1.000 is an **upper bound**, not a recall
figure on independent photographs.

`GET /v1/capabilities` still reports `LOCAL_CORRESPONDENCE available=False`
("No SIFT/SuperPoint/LoFTR. Product correspondence is a later wave.") while
ORB is answering.

**Verdict.** The measurement **holds**, with the manifest's honest limit,
and with a capability lie in the other direction.

### 5. A false counterfeit accusation was removed: unequal label-region perceptual hashes were treated as a hard product-code contradiction

**Command.** `verify_claims.check_label_hash_not_counterfeit` and
`tests/unit/test_label_hash_is_not_a_code.py` (inside the 95).

```text
assess_labels(ref="aaaa1111", cand="bbbb2222")
hard == []
missing == ["label-code-unresolved"]
"STRONG_COUNTERFEIT" not in src/searcher/authenticity/labels.py
```

**Verdict.** Holds.

### 6. Four separate paths assumed footwear; a garment was asked for its sole

**Command.** `verify_claims.check_four_footwear_paths`.

| Path | Garment / unknown | Sole? |
|---|---|---|
| `reference/gaps.py` `_priority_for("garment")` | front, rear, label, detail | **no** |
| `_priority_for(None)` / `"bag"` | garment list | **no** |
| `classify_listing_view(..., category="garment"\|None)` | `front` | n/a |
| `profile_for("garment").expected_views` | front, rear, lateral, label, detail | **no** |
| `published_compare_parts([eyelets,outsole,heel,...], garment)` | collar, label, front; construction unestablished | **no** |

Remaining footwear defaults, still in the tree:

- `ontology_for(None)` returns `FOOTWEAR_ONTOLOGY`
- `matching/pipeline.py` still does `ontology or ontology_for("footwear")`

**Verdict.** The four user-facing paths **hold**. Two silent defaults remain.

### 7. Replica language cannot publish as Real, including homoglyph and digit obfuscation, and is property-tested

**Command.** Attack A; `verify_claims.check_replica_cannot_publish_real`;
`tests/property/test_publication_invariants.py::test_generated_replica_text_never_reaches_real`
(220 examples; inside the 95).

| Text | `self_declared_replica` | published |
|---|---|---|
| `This is a replica` | true | replica |
| `repliсa` (Cyrillic es) | true | replica |
| `re\u200bplica` | true | replica |
| `r e p l i c a` | true | replica |
| `rep1ica` | true | replica |
| `not legit` / `god batch` / `dup` | true | replica |
| **`r3pl1ca`** | **false** | **Possibly Real** via router; **Real** if a Real decision is forced through `published_public_bucket` |

The property test's digit step maps `e→3, a→4` (`r3plic4`), not `i→1`.
`_despaced` maps `1→l`, so `r3pl1ca` becomes `repllca` and misses
`replica`.

**Verdict.** Homoglyph / ZWSP / spacing / the generated digit class **hold**.
Natural leet `r3pl1ca` **does not**. Attack A did not reach Real.

### 8. A public card requires an http(s) link and at least one reason code

**Command.** Attack D; `test_publish_requires_link.py`;
`test_a_result_without_reason_codes_is_never_published`.

| Case | Public rows |
|---|---:|
| empty URL + empty reasons | 0 |
| `javascript:alert(1)` | 0 |
| https URL + empty `reason_codes` | **0** (was 1 in round 3) |
| routed honest listing | 1, with link and `Reason codes:` |

**Verdict.** Holds. The round-3 reason-code leak is closed.

---

## Four attacks

Recorded in `artifacts/grading-round4/attacks.json`.

### Attack A — publish a replica to Real

13 + 30 committed phrases plus extras, given perfect match and authenticity
scores under `matching-1`, then forced through `published_public_bucket`.

- Reached Real: **[]**
- Replica-family (`yupoo`) with a stored Real decision: published `replica`
- Clean listings (`faux fur`, `fake leather`, `Authentic Prada`) unflagged
- **`r3pl1ca` published Possibly Real** (`self_declared_replica` is false)
- `Copy of the original receipt included` published Possibly Real (intended)

**Outcome.** Failed to reach Real. Succeeded in putting undeclared leet
(`r3pl1ca`) on Possibly Real, which `SEARCHER_BUCKET_POLICY.md` forbids
for a replica listing.

### Attack B — reach COMPLETE without fetching

| Case | State | Reason |
|---|---|---|
| empty campaign | `BLOCKED` | no usable query was compiled |
| query compiled, no source work | `BLOCKED` | no source work was planned |
| source marked completed, `pages_fetched=0` | `BLOCKED` | nothing was fetched |
| `forced=COMPLETE` | `COMPLETE` | internal override only |

**Outcome.** Blocked on the public path.

### Attack C — make a capability lie

| Case | available | lie? |
|---|---|---|
| dummy / empty / missing weights, probed or not | false | no |
| `probe_capabilities()` dummy (HTTP path) | DENSE_FEATURES false | no |
| real `embedding.pt`, no torch, `probe=True` | false | no |
| `record_probe_result(True)` cache poison | true | yes, internal only |
| `NEXT_VIEW` | **true**, no load/run probe | advertised without a probe |
| `LOCAL_CORRESPONDENCE` with opencv installed and ORB answering | **false** | yes, the other way |

**Outcome.** Blocked for DENSE_FEATURES. `NEXT_VIEW` is still advertised
without a probe. `LOCAL_CORRESPONDENCE` denies a detector that is running.

### Attack D — publish without a reason or a link

| Case | Public rows | link | reasons |
|---|---:|---|---|
| empty URL + empty reasons | 0 | — | — |
| `javascript:alert(1)` | 0 | — | — |
| https + empty reasons | **0** | — | — |
| routed honest listing | 1 | present | present |

**Outcome.** Both leaks are closed on the public path.

---

## §39 terminal deliverables

Present under an alias or the exact name:

- `ARCHITECTURE.md`, `SOURCE_POLICY.md`, `SEARCHER_AUTHENTICITY_POLICY.md`,
  `SEARCHER_BUCKET_POLICY.md`, `SECURITY.md`, `PRIVACY.md`,
  `LIMITATIONS.md`, `docs/SEARCHER_BENCHMARK_METHOD.md`,
  `docs/SEARCHER_PUBLIC_BENCHMARK_REPORT.md`, `SEARCHER_FINAL_SCORECARD.md`
- `artifacts/searcher-performance.receipt.json`,
  `artifacts/searcher-public-benchmark.receipt.json`

Missing at the names the Bible lists:

- `SEARCHER_SOURCE_AUTHORITY.md`, `SEARCHER_REUSE_LEDGER.json`,
  `SEARCHER_DATA_MODEL.md`, `SEARCHER_UX_SPEC.md`,
  `SEARCHER_PERFORMANCE_BASELINE.md`, `SEARCHER_RELEASE_READINESS.md`,
  `SEARCHER_TERMINAL_REPORT.md`
- `artifacts/searcher-source-authority.receipt.json`,
  `artifacts/searcher-reuse-ledger.receipt.json`,
  `artifacts/searcher-clean-clone.receipt.json`,
  `artifacts/searcher-security.receipt.json`,
  `artifacts/searcher-terminal.receipt.json`

---

## STATUS

NOT_READY.

## CLAIMS

1. Pages + tunnel + working public card: **HOLD** on a Willy snapshot; **FAIL**
   on the first-run shoe fixture; Real remains empty.
2. Self-sufficient reach / registry plan / second shop: **HOLD** for a
   dedicated Rebag campaign; **FAIL** for the default API campaign
   (`rebag=SOURCE_UNAVAILABLE` at 20s).
3. Wall time 199474 → 95705 median of three: **FAIL** as a reproduced
   number. Independent after median is **107146ms**. Overlap of host
   start times **HOLD**.
4. ORB TPR 1.000 / FPR 0.000 vs fallback noise: **HOLD** (upper bound on
   warped fixtures). Capability endpoint still denies correspondence.
5. Label-hash counterfeit accusation removed: **HOLD**.
6. Four footwear paths no longer ask a garment for a sole: **HOLD**.
   Two code defaults still assume footwear.
7. Replica cannot publish Real, including homoglyph and digit
   obfuscation, property-tested: **HOLD** for Real and for the generated
   class; **FAIL** for `r3pl1ca` on Possibly Real.
8. Public card needs http(s) + a reason code: **HOLD**.

## EVIDENCE

- `artifacts/grading-round4/test_all.log`
- `artifacts/grading-round4/live_campaign.log`
- `artifacts/grading-round4/targeted_unit.log`
- `artifacts/grading-round4/ruff.log`, `mypy.log`, `benchmark-all.log`, `scrub.log`
- `artifacts/grading-round4/verify_claims.json` + `.stdout.txt`
- `artifacts/grading-round4/orb_measure.json`, `fallback_measure.json`
- `artifacts/grading-round4/live_rebag.json`
- `artifacts/grading-round4/pages_tunnel.willy.json`, `pages_tunnel.trainer_a.json`
- `artifacts/grading-round4/attacks.json`
- `artifacts/grading-round4/stage_latency.after.json`
- `artifacts/grading-round4/scores.json`

## CHANGES

This lane wrote only `docs/grading/ROUND_4.md` and `artifacts/grading-round4/`.
`migrations/`, `docs/architecture/`, `fixtures/`, and two receipts were
materialized from `git archive HEAD` so the floor commands could run; they
were not edited. Benchmark-rewritten fixture PNGs and receipts were restored.

## TESTS

See Floor commands. Isolated correspondence / replica / publication /
label-hash / gap-view tests passed. The one-process floor suite did not.

## RISKS

- SIGSEGV on `subprocess` after a live/API wave (G039-class). `test_all.sh`
  documents this for `live_campaign`; it now also hits the fast suite once
  tesseract and `searcher serve` have been spawned.
- System resolver on this host cannot resolve `*.trycloudflare.com` even
  though 1.1.1.1 can. A stranger whose stub resolver behaves like this
  Mac's would see the tunnel as down.
- Default 20s source deadline makes `rebag` look unavailable even though
  a dedicated 180s campaign retrieves it.
- `LOCAL_CORRESPONDENCE` and `NEXT_VIEW` capability records do not match
  what the process can actually do.

## UNRESOLVED

- Nothing reaches Real.
- `r3pl1ca` on Possibly Real.
- Default campaign never returns `shop.rebag.com`.
- Floor suite is not green in one process.
- Named §39 files and receipts still missing.
- DINOv2 0.771 not reproduced without torch + weights.
- `ontology_for(None)` still returns footwear.

## NEXT

Smallest path to a status other than `NOT_READY`:

1. Let a planned Rebag fetch finish inside the API source deadline, or
   stop calling a deadline miss `SOURCE_UNAVAILABLE` when the shop
   answers a dedicated run.
2. Fold `r3pl1ca`-class leet into `self_declared_replica` and the
   generated property test.
3. Make `./scripts/test_all.sh` survive child spawn after a live wave
   (isolate tesseract / `searcher serve` the way `live_campaign` is
   already isolated).
4. Put one live garment in Real, or drop §40.15 from the public claim.
5. Add the missing §39 filenames, or change the Bible list to the aliases
   that already exist.

Until 1–4 are independently re-run and the critical scores are ≥ 90,
the terminal status stays `NOT_READY`.
