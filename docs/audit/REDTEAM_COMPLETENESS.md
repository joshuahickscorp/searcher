# Red-team report: Searcher’s claim of completeness

**Lane:** searcher-redteam (read-only against `src/`, `tests/`, `scripts/`, `web/`, `fixtures/`, `pyproject.toml`)  
**Tree:** `e1716058a93a31c6252f6f54867beb817e30b25a`  
**Date:** 2026-08-16  
**Method:** `git show` / `git grep` on HEAD; invariant attacks and receipt reruns against a `git archive` copy at `/tmp/searcher-rt-exec` (this worktree is a sparse checkout: `src/` is not on disk).  
**Suite on the archive:** `316 passed, 5 skipped, 1 deselected` plus `1 passed` live-campaign.  
**Suite in this sparse worktree:** cannot import `searcher` (`ModuleNotFoundError`). That is a checkout limit, not a product defect.

Bible authority: `docs/SEARCHER_FULL_IMPLEMENTATION_BIBLE.md` §§3, 10.2, 20, 38, 40, 41.

---

## Verdict

**This is not honestly a private alpha under the Bible.**

README is more careful than the surrounding claims: it says **pre-alpha 0.1.0**. Wave 13’s gate (a stranger uploads references, gets streamed results, understands the two tabs, opens live links, inspects comparison evidence, deletes the search) is only half true. Comparison evidence is published as an empty list. The flagship Dior search in the operator receipt finished with **Real 0, Possibly Real 0**. The one live “ranked first” run put a KIND cutsew in Possibly Real, not Real, and never compared images.

**The single most dishonest thing still in the tree** is the terminal state `COMPLETE` / `"coverage exhausted"` on a campaign that fetched nothing. That is not a leftover comment. It is the default branch of `_choose_terminal`, it is how unused queries are stamped `EXHAUSTED`, and it is exactly the stored adversarial-recall receipt: **0/21 found, 21 × COMPLETE in 2.02s**.

Wrong answers outrank that for a user. Thirteen ordinary self-declared-replica phrases route and publish as **Real** once scores clear the Real gate.

---

## Ranked findings

Rank: **wrong answers** first, **dishonest states** second, **missing / narrowed scope** third. Every row has a command or `file:line`. A finding without one is not in this table.

| # | Rank | Finding | Claims | Actually | Proof |
|---|---|---|---|---|---|
| 1 | Wrong answer | Self-declared replica listings reach **Real** | UI and API copy: “A replica listing can never be ranked Real.” | 13 phrases (`This is fake.`, `スーパーコピー レプリカ`, `dupe`, `superfake`, `PK God`, `UA batch`, fullwidth `1：1`, `not genuine`, `mirror batch`, `homage`, `AAA+ batch from the factory`, `Inspired by…`, `repsneaker quality`) route `public=real` and publish `real` when item/auth lower bounds are 0.91. Detector only looks at title+description against 11 English-centric regexes. Tests only cover `"Unauthorized replica 1:1"`. | `uv run python` attack → `artifacts/redteam-replica-real-gate.json` (`LEAKED_TO_REAL 13`). Patterns: `src/searcher/retrieval/text.py:36-48,99-102`. Routing: `src/searcher/ranking/vetoes.py:86-87`, `src/searcher/campaigns/publication.py:22-32`. Copy: `src/searcher/api/views.py:343`, `web/index.html:31,131`. Tests: `tests/unit/test_replica_routing.py:29`. |
| 2 | Wrong answer | Embedding operating point does not separate same-type garments | Receipt: DINOv2 24/28 top-1, FPR 0.0094 at 0.86. Realmatch cites `ev:embedding:cosine`. | On the fixtures the calibrator actually writes (`fixtures/known_item_kind`, 10 listings / 30 images / 30 pos / 90 neg) negative **median 0.8773 > positive median 0.8534**. At code threshold 0.86: TPR 0.47, **FPR 0.59**. Stored 59/1711 gallery is not in the tree. | `artifacts/redteam-calibration-rerun.json` vs `artifacts/searcher-match-calibration.receipt.json`. Command: embed every fixture image with local `embedding.pt` + DINOv2 identity, then cosine pairs. `src/searcher/core/embedding_gateway.py:27` `OPERATING_THRESHOLD = 0.86`. |
| 3 | Wrong answer | “A search returns the source listing ranked first” is one Possibly Real hit, not Real, and not the flagship | Task brief / realmatch lane. | `artifacts/realmatch/known_item_summary.json`: `target_in_real_rank: null`, `target_in_possibly_real_rank: 1`, title `無地 ロングスリーブカットソー`, authenticity **identical** 0.52 / 0.40 / 0.586 on all three public hits, `images_compared: []`, `reason: null`. Operator clean-clone of the Dior GAT query: Real 0, Possibly Real 0, hidden 8 (`artifacts/operator/search-final.json`). | `python3 -c "…known_item_summary.json…"`; `artifacts/operator/RECEIPT.md` “First search”. |
| 4 | Wrong answer | Authenticity is a bin, not a measurement, on this live set | Three judgments, calibrated intervals. | Footwear table maps every raw mean in `[0.45, 0.62)` to **cal_mean 0.52, lo 0.4, hi 0.586** — exactly the three realmatch cards. Non-footwear construction returns a constant 0.5 (`construction.py:20`). Generic profile expects view `"unknown"` (`profiles/base.py:24`), which then appears as missing evidence. | `artifacts/redteam-invariant-attacks.json` `authenticity_bins`; `fixtures/calibration/footwear_v1.json` bins; `src/searcher/authenticity/construction.py:20-22`; `src/searcher/authenticity/profiles/base.py:20-24`. |
| 5 | Dishonest state | `COMPLETE` / “coverage exhausted” with zero work | Bible §10.2: COMPLETE requires exhaustion or saturation. Bible §3.8: do not convert not-attempted into “no results.” CLAIMS.md 15: do not invent a successful empty search. | Default `_choose_terminal`: empty coverage, no candidates, discovery imported → `COMPLETE, "coverage exhausted"`. Just before that, every `QUEUED`/`RUNNING` query is rewritten to `EXHAUSTED`. Receipt field `queries_exhausted = sum(EXHAUSTED) or len(queries)` treats 0 as “all of them.” Stored recall: 21 × COMPLETE in 2.02s, 0 fetches implied. | `src/searcher/campaigns/orchestrator.py:1415` default; `:1428-1432` mark exhausted; `:1344-1345` `or len(queries)`. Attack: `artifacts/redteam-invariant-attacks.json` `complete_zero_fetches`. Receipt: `artifacts/searcher-adversarial-recall.receipt.json`. |
| 6 | Dishonest state | Capability `available: true` while the call returns nothing | Probe “reflects the real probe; does not invent lanes.” | Dummy `embedding.pt` (8 bytes of garbage): `find_local_weights()` hits, `resolve_backend()` returns DINOv2 identity, `embedding_capability().available is True`, `embed_png()` returns `None`. `GET /v1/capabilities` `discovery`/`routing` are true if the modules import (`layers_present`, `orchestrator.py:125-141`), not if a fetch happens. `NEXT_VIEW` is hard-coded `available=True` for a missing-view heuristic. | `artifacts/redteam-invariant-attacks.json` `capability_vs_call.dummy_weights`. `src/searcher/core/embedding_gateway.py:59-61,96-128`. `src/searcher/integrations/visionmcp/probe.py:169-181`. Operator receipt already noted dummy weights + `embed_png is None`. |
| 7 | Dishonest state | Every public result is published with `images_compared: []` | Bible §3.10: every result answers which images were compared. | `project_result` hard-codes the field. Decision `explanation.compared_images` is never copied. Realmatch cards therefore cannot show a comparison. | `src/searcher/api/views.py:363`. `git grep compared_images -- src/searcher/api/views.py` → no other hit. `artifacts/realmatch/results.json` `"images_compared": []`. |
| 8 | Dishonest state | Soak and abuse “all honest / no leak” never run discovery | “38 abuse cases all behave honestly”; “soak shows no leak”. | `tests/support/live_api.py:74` sets `SEARCHER_LIVE_DISCOVERY=0`. Soak **asserts** every search is `BLOCKED` (`test_api_soak.py:94,121`). Abuse table has **36** rows, not 38. Soak RSS in JSON is 90128; hardening doc says 89008. | `python3 -c "len(json.load(open('artifacts/hardening/abuse-table.json')))"` → 36. `artifacts/hardening/soak.json` `"all_blocked": true`. `docs/hardening/NONDETERMINISM_AND_ABUSE.md` after-50 RSS 89008. |
| 9 | Dishonest state / evidence | Load-bearing receipts do not regenerate | Calibration, performance, recall, clean-clone. | See receipt section below. DINOv2 24/28 has **no runner in HEAD**. Recall receipt has **no runner in HEAD**. Performance HTTP warm 258ms → **43525ms**; HTTP cold wall **null**. Clean-clone receipt is SHA `a66414e`, not `e171605`. “About 128 seconds” is a subset of measured **310.44s**. | `artifacts/redteam-receipt-comparison.json`. `git ls-tree -r --name-only HEAD \| rg -i recall` → only the JSON. `scripts/calibrate_embeddings.py` writes a different schema than the stored file. |
| 10 | Dishonest state | “Scrub passes and history is clean” | Task brief. | Working tree scrub PASSes. History is **not** clean: 47 `$HOME` hits, 4 home-path hits. The script does not fail on history unless `SEARCHER_SCRUB_FAIL_ON_HISTORY=1`. | `./scripts/scrub_public_tree.sh` → `PASS: working tree is clean` plus `GIT HISTORY` counts. |
| 11 | Missing / narrowed | Docs still describe a product that does not match the code | ARCHITECTURE, CLAIMS, LIMITATIONS, EMBEDDINGS, API. | `ARCHITECTURE.md:60-63` says the served API stops `BLOCKED` because discovery is **not wired** and `run_api.sh` does not invoke later stages. `LIMITATIONS.md:97` and `scripts/run_api.sh` turn live discovery **on**. `CLAIMS.md:47-50` and `LIMITATIONS.md:40-45` say matching is classical and there is **no learned backbone**; `src/searcher/retrieval/embeddings.py` and `BACKBONE_IDENTITY = "facebookresearch.dinov2.vits14"` are a learned backbone when weights exist. `docs/architecture/EMBEDDINGS.md:3` still says ResNet50. `docs/architecture/API.md:28` says `SEARCHER_EMBEDDING_WEIGHTS` “this version does not load it.” UI still says “current benchmark” (`web/index.html:129-130`); LIMITATIONS admits no benchmark has been run. | Commands: `git grep` as listed. |
| 12 | Missing / narrowed | Job-scraper adapter fetch is a stub | Donor reuse / discovery. | `InProcessJobScraperAdapter.fetch_candidates` and `NullJobScraperAdapter.fetch_candidates` both `del urls; return []`. Live discovery uses `DiscoveryEngine`, not this fetch. The adapter still sits in the tree as if it fetches. | `src/searcher/integrations/job_scraper/adapter.py:57-59,84-86`. |
| 13 | Missing / narrowed | Completeness used for routing is an image-count heuristic | Bible §19.5 view completeness. | Orchestrator `_rank` sets `complete = 0.4 if candidate.images else 0.15`, then pads by image count (`orchestrator.py:1003-1006`). It does not call `authenticity.completeness`. Combine also floors the item-match **upper** at `max(mean, 0.55)+0.04` (`matching/combine.py:51`). | Those lines. |
| 14 | Missing / narrowed | Source-scope “both scopes” receipt never finished | Scope work. | `artifacts/source-scopes/both-scopes-runtime.json` is `{"terminal": null, ...}`. | `python3 -c "print(json.load(open('artifacts/source-scopes/both-scopes-runtime.json')))"`. |
| 15 | Missing / narrowed | International / replica marketplaces are registered and disabled | Adapter manifests. | Vinted, Mercari JP, Yahoo, Buyee, Bunjang, SSENSE, Farfetch, StockX, GOAT, Poshmark, DDG, Grailed, Vestiaire, Depop, Taobao, Weidian, Yupoo: `enabled=False` or `PendingReviewAdapter.discover` returns `BLOCKED_BY_POLICY` without I/O. Honest in LIMITATIONS; still looks like coverage in the adapter list. | `src/searcher/sources/adapters/product.py` `enabled=False` rows; `src/searcher/sources/adapters/pending.py:56-65`. |

---

## Category sweep

What was searched, and whether the category is clean.

### Placeholders, `TODO`, `FIXME`, `pass  # later`, `NotImplementedError`

**Mostly clean as tokens.** `git grep -E 'TODO|FIXME|NotImplementedError' HEAD -- src/` hits `matching/synth.py` (`XXXXXX` label codes) and `normalization/size.py` (`XXXL`). No `NotImplementedError` in `src/`.

What exists instead of a `TODO` is **honest-looking refusal that still presents as a finished lane**:

- VisionMCP `retrieve_candidates` / `compare_candidate` raise `CapabilityUnavailable` (`src/searcher/integrations/visionmcp/adapter.py` comments: “Do not return placeholder scores”).
- Wave-1 `CapabilityRegistry` still installs every perception name as `available=False` with note “Wave 1 constitution only; probe lands in a later wave” (`src/searcher/core/capabilities.py`). The API uses `probe_capabilities()`, so this registry is leftover constitution, not what `/v1/capabilities` returns — except `NEXT_VIEW` is then re-marked available (finding 6).

### Functions returning a constant, empty list, or input unchanged

**Not clean.** Load-bearing ones:

| Location | What it returns | Why it matters |
|---|---|---|
| `job_scraper/adapter.py:57-59,84-86` | `[]` | Adapter named as if it fetches. |
| `api/views.py:363` | `images_compared: []` | Always, for every result. |
| `authenticity/construction.py:20` | `scored(0.5)` | Non-footwear. |
| `authenticity/profiles/base.py:24` | `expected_views=("unknown",)` | Shows up as missing “unknown”. |
| `matching/combine.py:51` | upper ≥ 0.59 | Inflates the published interval. |
| Footwear bins `[0.45,0.62)` | `0.52 ± …` | All three realmatch auth cards. |
| `queries_exhausted = sum(...) or len(queries)` | “all queries” when none exhausted | Exhaustion receipt. |

Empty `return []` on adapters that truly have nothing to parse (bad HTTP, disabled, no seeds) is honest. `ProductPageAdapter.discover` returning `NOT_ATTEMPTED` / `"no seed paths"` when the query cannot be turned into a collection slug is how KIND can “search” in 2 seconds and report no match.

### Tests with no assertion, tautologies, mocks only

**Not clean**, after discarding detector false positives (nested `def` / `pytest.raises`).

| Test | What it actually checks |
|---|---|
| `tests/real_runtime/test_api_soak.py` | 50 searches, each must be `BLOCKED`. Discovery is forced off. |
| `tests/real_runtime/test_api_abuse.py` | Validation / cancel / SSE against the same offline process. |
| `tests/unit/test_embeddings.py::test_broad_and_match_use_embedding_score` | Monkeypatches `embed_png` to a stub vector. Does not load weights. |
| `tests/unit/test_replica_routing.py` / `test_replica_publication.py` | Only the English `"Unauthorized replica 1:1"` sentence. Those tests **pass** while finding 1 succeeds. Command: `uv run pytest tests/unit/test_replica_routing.py tests/unit/test_replica_publication.py` → pass; attack script → 13 Real leaks. |
| `tests/unit/test_source_scope_mutations.py` | Defines a local `broken()` and asserts that `broken()` is not the real function. Does not mutate production code. |

No `assert True` tautologies. Cancel / SSRF tests that the first scan flagged as “no assert” do contain `assert` (split on nested `def`).

### `skip`, `xfail`, broadened `try/except`, raised timeouts, loosened tolerances

**Mostly skip-on-missing-optional, not xfail.**

Skips (`git grep pytest.skip\|importorskip HEAD -- tests/`):

- embeddings / known-item offline: no local weights or no torch
- visionmcp adapter + compatibility: donor not installed
- browser leak: playwright missing or launch failed

No `xfail` in `tests/`. Soak marked `@pytest.mark.timeout(360)`. Live campaign `@pytest.mark.timeout(180)`.

Broad `except Exception: continue` appears in the orchestrator image download / store load paths (`orchestrator.py` around the `_reference_pngs` / `_candidate_pngs` loops). That swallows missing bytes and proceeds with fewer images — then publishes `images_compared: []` anyway.

`matching/combine.py:51` is a loosened upper bound, not a test tolerance.

### Evidence artifacts whose numbers no longer match a rerun

**Not clean.** See the receipt section. Also:

- Operator test count `250 passed, 3 skipped` vs archive run `316 passed, 5 skipped`.
- Soak RSS 90128 vs `docs/hardening/NONDETERMINISM_AND_ABUSE.md` 89008.
- Abuse 36 rows vs the “38 cases” brief.

### Documentation claiming behaviour the code does not have

**Not clean.** Finding 11. Additional copy:

- `web/index.html:129-130` “declared benchmark” / “current benchmark”.
- `CLAIMS.md` “Not entitled: that the engine has a learned visual backbone” while `1d04cb9` wired DINOv2 into matching and realmatch cites `ev:embedding:cosine`.
- `LIMITATIONS.md:47-50` “No precision, recall, leakage, or latency figure in this repository is a measured product result” sitting next to three numeric receipts in `artifacts/`.

### Paths that only ever execute against fixtures / never against a real source

**Not clean.**

- `live_api()` hard-disables discovery. Soak + abuse + most API integration tests never leave the process.
- `tests/unit/test_embeddings.py` stubs the backbone.
- Hard-negative suite is synthetic shoes (`searcher.matching.synth`).
- Performance **fixture** path (5 scripted listings) still works; the HTTP path in the same receipt is a different machine (finding 9).
- KIND “search” is collection-slug JSON, not `/search` (robots disallow). A Dior-shaped query becomes `/collections/dior-homme/products.json`. A Willy Chavarria query hits a real collection — that is why realmatch found something and the flagship Dior run did not.

---

## Invariant attacks (all five attempted)

Attacks were executed against HEAD code imported from a `git archive` copy. Results: `artifacts/redteam-invariant-attacks.json`, `artifacts/redteam-replica-real-gate.json`.

### 1. A replica candidate reaching Real

**Succeeded.** With Real-gate-passing scores (item/auth lower 0.91, completeness 0.8, live, destination verified, `matching-1`):

```text
This is fake.                         routed=real published=real
スーパーコピー レプリカ                 routed=real published=real
AAA+ batch from the factory           routed=real published=real
… dupe / superfake / PK God / UA …
1：1 (fullwidth colon)                routed=real published=real
not genuine / homage / mirror batch   routed=real published=real
```

13 / 13 undetected phrases published Real. Yupoo *family* still remaps to the replica tab (`family_for("yupoo") == replica`). Seller-brand-only `"replica factory"` is not read. The shipped tests still pass.

Command:

```bash
# from git-archive tree with src/ on PYTHONPATH
uv run python -c '…route_candidate + published_public_bucket…'
# output: artifacts/redteam-replica-real-gate.json
```

### 2. A campaign reporting COMPLETE with zero fetches

**Succeeded as a decision-table fact; matches the stored recall receipt.**

Empty coverage + no candidates + discovery not marked blocked → `COMPLETE` / `"coverage exhausted"` (`orchestrator.py:1415`). Combined with stamping unused queries `EXHAUSTED` (`:1428-1432`) and `queries_exhausted = n or len(queries)` (`:1344-1345`).

The stored file `artifacts/searcher-adversarial-recall.receipt.json` is 21 rows of that shape (2.02s, 0 results, COMPLETE). There is no runner in HEAD to regenerate it. `git ls-tree -r --name-only HEAD | rg -i 'adversarial.recall|recall_run'` → only the JSON.

### 3. A self-declared replica passing routing

**Succeeded.** Same as (1): `self_declared_replica()` is false, `collect_hard_vetoes` adds nothing, `route_candidate` returns `BucketPublic.REAL`, `published_public_bucket` does not remap.

### 4. A result published without a reason

**Succeeded for comparison evidence; partial for reason codes.**

- `images_compared` is always `[]` (`views.py:363`).
- Realmatch summary top-level `"reason": null`.
- Cards that *do* have a decision get `Reason codes: possibly-real-gate` appended to a stock sentence. That is a gate name, not “which images, which parts, what is missing” in Bible §3.10’s sense. Missing includes `"unknown"` from the generic profile.

### 5. A capability reporting available while the underlying call returns nothing

**Succeeded.**

```text
dummy embedding.pt (not TorchScript)
  find_local_weights → /tmp/…/embedding.pt
  resolve_backend    → facebookresearch.dinov2.vits14
  capability.available → True
  embed_png()        → None
```

`layers_present()["discovery"]` is True in this archive because `searcher.sources.engine` imports. That is also what `/v1/capabilities` reports. It is not a probe of robots, keys, or a successful fetch.

---

## Regenerated receipts

Three load-bearing receipts were rerun or shown to be unreproducible. Stored files were **not** overwritten.

### A. `artifacts/searcher-match-calibration.receipt.json`

| | Stored | Rerun on current fixtures + local DINOv2 weights |
|---|---|---|
| Listings | 59 (gallery) | 10 (`fixtures/known_item_kind`) |
| Pos / neg pairs | 59 / 1711 | 30 / 90 |
| Positive median | 0.8101 | 0.8534 |
| Negative median | 0.1606 | **0.8773** |
| Negative max | 0.9393 | 0.9717 |
| TPR @ 0.86 | 0.322 | 0.4667 |
| FPR @ 0.86 | 0.0094 | **0.5889** |
| DINOv2 top-1 | 24/28 | **no runner in HEAD** |
| ResNet50 top-1 | 14/28 | **no runner in HEAD** |

`scripts/calibrate_embeddings.py` today writes `{backbone, threshold, tpr, fpr, n_listings, …}`, not the stored gallery schema. `scripts/prepare_embedding_weights.py` repeats 24/28 in a docstring. Neither script can emit the stored file.

Command: `SEARCHER_EMBEDDING_WEIGHTS=/Users/…/data/models/embedding.pt` + vision interpreter; output `artifacts/redteam-calibration-rerun.json`.

### B. `artifacts/searcher-performance.receipt.json`

Command: `uv run python -m searcher.bench --output artifacts/redteam-performance-rerun.json` (archive tree).

| Field | Stored | Rerun |
|---|---|---|
| Fixture cold wall | 96.4 ms | 53.0 ms |
| Fixture warm wall | 75.2 ms | 34.8 ms |
| Fixture cold fetches / candidates | 5 / 5 | 5 / 5 |
| HTTP cold campaign wall | 1008.7 ms | **null** |
| HTTP warm campaign wall | 259.0 ms | **43525.4 ms** |
| HTTP warm first candidate | 259.0 ms | **39815.2 ms** |
| HTTP first routed result | null | null |

The fixture/index path still answers. The HTTP path in the same receipt is not a stable number and still never records a routed result.

### C. `artifacts/searcher-adversarial-recall.receipt.json`

No command exists. Stored shape (0/21, COMPLETE, 2.02s) is explained by finding 5. Not regenerated; not rewritten.

### Bonus: operator clean-clone and hardening

- `artifacts/operator/RECEIPT.md` is SHA `a66414e`. HEAD is `e171605` (`git log --oneline a66414e..HEAD` is a long list). “About 128 seconds” vs measured `clone_to_search 310.44s`. First search: 0 public results.
- Abuse JSON: 36 honest rows, discovery off.
- Soak JSON: 50 × BLOCKED, discovery off; RSS disagrees with the hardening doc by ~1.1 MB.

---

## Wave grades (Bible §38.1)

Score 0–100. Critical-wave floor is 90 on plan fidelity, implementation completeness, real-runtime proof, security/privacy, authenticity safety, test quality. User-visible product waves also need user-visible proof ≥ 90.

| Dimension | Score | Why, if below 90 |
|---|---|---|
| Plan fidelity | **58** | Bible §8.2 / §40 require part-level compare, live Real/Possibly Real for the Dior flagship, search-exhaustion that is real, and explainable results. Architecture still says discovery is unwired. Flagship receipt is empty public lists. `images_compared` is a stub. COMPLETE is the empty-coverage default. |
| Implementation completeness | **62** | Packages exist and import. Fetch adapter returns `[]`. Half the adapter registry is `enabled=False`. Completeness used for routing is image-count. Generic profile expects `"unknown"`. Learned backbone exists but is optional, undocumented as ResNet50, and contradicted by CLAIMS. |
| Real-runtime proof | **45** | One KIND shirt in Possibly Real; Dior GAT 0/0; recall 0/21 COMPLETE in 2s; soak/abuse never discover; performance HTTP wall null / 43s; calibration gallery gone. |
| User-visible proof | **64** | Pages UI exists, SSE exists, two tabs exist, delete works. Comparison evidence is empty. UI still mentions a benchmark. Replica copy is false. A stranger following OPERATING.md can search and honestly get nothing. |
| Retrieval quality | **38** | Current fixture FPR 0.59 at the shipped threshold; negative median > positive median; 0/21 recall receipt; KIND cannot query `/search`; Dior slug is a collection that does not hold the item. |
| Authenticity safety | **42** | Finding 1 is a P0 against Bible §20 / SOURCE research (“self-declared fakes never appear on Real / Possibly Real”). Footwear bin collapses live garment scores to 0.52. Price is correctly unable to promote; that is not enough. |
| Security and privacy | **82** | SSRF matrix, upload magic-bytes, deletion 404, no hosted API, Job Scraper §6.10 rejected. Soak/abuse are offline. Scrub tree-pass hides dirty history. No auth on the process (documented). Below 90 because live discovery is not what the hardening receipts exercised. |
| Cost efficiency | **78** | Cheap-first and warm index are real on the fixture path. HTTP bench no longer matches the receipt. 2s COMPLETE is cheap because it did not search. |
| Test quality | **60** | 316 passing tests on the archive is real. The tests that would have caught findings 1, 5, 6, 7 do not exist or test the inverted-discovery path. Replica tests are a single English sentence. Soak asserts BLOCKED. Embeddings are mocked. Mutation tests do not mutate. |
| Documentation | **55** | CLAIMS / LIMITATIONS / ARCHITECTURE / EMBEDDINGS / API / UI / receipts cannot be true at the same time. README’s “pre-alpha” is the most accurate sentence in the tree. |

**No critical dimension is ≥ 90.** Under §38.2 the current wave is not complete.

Terminal status per §39: **`NOT_READY`**, not `PRIVATE_ALPHA_READY`.

---

## Named claims, checked

| Claim | Result |
|---|---|
| A search returns the source listing ranked first | One KIND URL in **Possibly Real**, rank 1. Not Real. Flagship Dior: 0 public. |
| DINOv2 beats ResNet50 24/28 vs 14/28 | Unreproducible. No runner. Current fixtures do not support the stored FPR. |
| 38 abuse cases all behave honestly | **36** rows. All marked honest. All on `LIVE_DISCOVERY=0`. |
| Soak shows no leak | 50 × BLOCKED, discovery off. RSS disagrees with the doc. No live-fetch leak was measured. |
| A replica listing can never be ranked Real | **False.** 13 phrases reach Real. |
| The scrub passes and history is clean | Tree passes. History is not clean (47 `$HOME`, 4 home paths). |
| Clean clone ~128 seconds | Receipt SHA is old. Measured clone→search is 310s. Search itself ~125s, **0 public results**. |
| Adversarial recall 0/21 COMPLETE in 2s | Still the most compact picture of finding 5. No runner to replay. |

---

## What this lane did not change

Nothing under `src/`, `tests/`, `scripts/`, `web/`, `fixtures/`, or `pyproject.toml`.

This worktree created `.venv/` as a side effect of `uv run` (gitignored). Required `./scripts/test_all.sh` here fails with `No module named 'searcher'` because `src/` is not materialized. The same command on a `git archive` of HEAD: **316 passed, 5 skipped**.

`uv run ruff check .` in this worktree: **All checks passed.**  
`uv run mypy src` in this worktree: cannot read `src`. On the archive: **Success: no issues found in 251 source files.**

Supporting outputs (this lane only):

- `docs/audit/REDTEAM_COMPLETENESS.md` (this file)
- `artifacts/redteam-invariant-attacks.json`
- `artifacts/redteam-replica-real-gate.json`
- `artifacts/redteam-calibration-rerun.json`
- `artifacts/redteam-performance-rerun.json`
- `artifacts/redteam-receipt-comparison.json`
