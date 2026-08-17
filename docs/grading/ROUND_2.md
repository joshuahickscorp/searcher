# Round 2 independent regrade

Graded 2026-08-17 against Bible §38 / §39 at commit
`6435d248a716429f197e807627c126b73f30efc5`. This pass did not write `src/`,
`tests/`, `scripts/`, `web/`, `benchmark/`, `fixtures/`, or `pyproject.toml`.
Commands below were run in this worktree. Stored receipts, commit messages,
and the previous `docs/grading/ROUND_2.md` (which graded `a7a5a98`) were
treated as claims, not evidence.

§39 terminal status: **NOT_READY**.

No critical §38.2 dimension reaches 90. User-visible proof is also below 90.
Nothing in a live campaign reached Real (§40 behaviour 15). Residual replica
language that is not in the committed 13+30 lists still publishes to
Possibly Real. `benchmark --all` without local DINOv2 weights does not
reproduce the cited 0.771 / 70% figures.

---

## Round-2 scores

These are the scores this pass assigns to `6435d24`. Round 1 is from the
scorecard (commit `6c4c5e3`). The `a7a5a98` column is the previous
independent pass, kept for comparison only.

| Dimension | R1 | a7a5a98 | **This pass** | One-line justification |
|---|---:|---:|---:|---|
| Plan fidelity | 58 | 70 | **78** | Ranking, COMPLETE, capability probe, publish-link, category views, and honest flagship-21 now match the plan; §40.15 still fails, Dior is still substituted, §39 named files are still missing. |
| Implementation completeness | 62 | 73 | **80** | Live garments score completeness 0.80 not 0.40; ranking, size/brand, and the link gate work; Real remains unreachable (auth lower bound 0.40) and compare still reports eyelets/outsole/heel on a shirt. |
| Real-runtime proof | 45 | 71 | **77** | Fast suite 458 passed in 51.28s; live campaign 1 passed in 132.17s; independent KIND and Willy runs published ranked live links; soak/abuse still force `SEARCHER_LIVE_DISCOVERY=0`; stored adversarial recall is still 0/21. |
| User-visible proof | 64 | 73 | **84** | Null and `javascript:` URLs stay hidden; live cards carry `https` links, reason codes, and compare; inserting empty `reason_codes` still publishes; Real is empty; crops and hypotheses are still not in the API. |
| Retrieval quality | 38 | 64 | **73** | DINOv2 recall@1 0.771 / recall@5 1.0 reproduced; synthetic Prada at feed position 104 and the live Willy target are taken first of 24; shipped 0.86 still admits 70% of different-listing pairs. |
| Authenticity safety | 42 | 83 | **88** | All 13 + 30 listed phrases publish as `replica`, never Real; "copy of the original receipt" stays clean; `not legit`, homoglyph `repliсa`, `god batch`, and `dup` still reach Possibly Real. |
| Security and privacy | 82 | 83 | **83** | SSRF, upload, and deletion tests are inside the 458 that passed; working-tree scrub exits 1 (198 hits); history is still dirty; soak/abuse do not exercise live fetch. |
| Cost efficiency | 78 | 80 | **81** | Fixture warm-index cache-hit 1.0 and duplicate-work 1.0 reproduced; a live API-bounded Willy campaign took 197s and stopped on budget with 2 published results. |
| Test quality | 60 | 76 | **85** | 458 + 1 live passed; mypy passes with torch absent; 30 replica phrases, publish-link, views, size, and generic profile are regression tests; soak still asserts `BLOCKED`; residual slang and reason-less publish are untested. |
| Documentation | 55 | 77 | **80** | Nine files exist and a revert of a guarded sentence fails the test; "shortlist cut, not an identity gate" and the 70% FPR live only in a code comment; LIMITATIONS still says the generic profile is empty. |

Critical floor is 90 (§38.2): plan fidelity, implementation completeness,
real-runtime proof, security/privacy, authenticity safety, test quality.
A user-visible product wave also needs user-visible proof ≥ 90. None of
those cleared.

---

## Floor commands

| Command | Result |
|---|---|
| `./scripts/test_all.sh` | Fast suite **458 passed, 6 skipped, 1 deselected in 51.28s**. Live campaign **1 passed, 464 deselected in 132.17s**. Wrapper exit 0. Log: `artifacts/grading-round3/test_all.log`. |
| `uv run ruff check .` | `All checks passed!` (re-checked after this lane's artifact scripts). |
| `uv run mypy src` | **Passes without torch installed.** `Success: no issues found in 262 source files`. `importlib.util.find_spec("torch")` was `False` in the same environment. Log: `artifacts/grading-round3/mypy.log`. Vision extra was installed only later, for DINOv2 receipt regeneration. |
| `uv run python -m benchmark --all` | Runs. Without weights: recall@1 **0.914286**, scorer `searcher.cheap_visual.ahash_colour`. With `SEARCHER_EMBEDDING_WEIGHTS` pointing at the host DINOv2 file: recall@1 **0.771429**, MRR **0.866667**, false Real **0** — headline numbers match the stored receipt. Also rewrote two committed fixture PNGs; they were restored from `git show HEAD:…` so the tree is not left dirty. |
| `uv run python -m benchmark.threshold` | Without weights: shipped 0.86 held-out FPR **0.0**, verdict "holds". With DINOv2: shipped 0.86 held-out TPR **0.5**, FPR **0.7**, verdict **"chosen threshold does not hold on held-out data"** — matches the stored receipt. |
| `./scripts/scrub_public_tree.sh` | Exit **1**. `FAIL: 198 working-tree finding(s)`. History still has `$HOME` / home-path hits. Committed working-tree hits include `docs/audit/REDTEAM_COMPLETENESS.md` and the previous `docs/grading/ROUND_2.md`. This lane's logs under `artifacts/grading-round3/` added more home-path findings. |
| `git status --porcelain` | Allowed dirty paths under `docs/` and `artifacts/` only. Fixture PNGs were restored after `benchmark --all` rewrote them. |

Fast-suite timing claim of 52s is **51.28s** here. Live-campaign timing claim
of ~130s is **132.17s** here.

---

## Claim checks

Each claim was run through something that would fail if it were false.

### 1. Thirty extra replica phrasings are now detected, including zero-width and spaced-out obfuscation; "copy of the original receipt" is not a replica

**Command.** `uv run python artifacts/grading-round3/verify_claims.py` and
`uv run python artifacts/grading-round3/attacks.py`, plus
`uv run pytest -q tests/unit/test_replica_phrases.py`.

**Result.** `LEAKED_ROUND_TWO` in `tests/unit/test_replica_phrases.py` has
**30** strings, including `re\u200bplica` and `r e p l i c a`. All 30
return `self_declared_replica is True`. Routed with perfect scores they
publish as `replica`, never Real, never Possibly Real.

`Copy of the original receipt included` and `comes with copy of the original
invoice` return False and stay off the replica list.

**Verdict.** The stated claim holds. See Attack A for residual phrases that
are not in this list.

### 2. A public bucket requires a usable http or https link; null or javascript: stays hidden

**Command.** `verify_claims.check_publish_requires_link` and Attack D.

**Result.**

| URL | `has_usable_listing_link` | published Real / Possibly Real |
|---|---|---|
| `""` / null | false | hidden / hidden |
| `javascript:alert(1)` | false | hidden / hidden |
| `data:text/html,x` | false | hidden / hidden |
| `/products/1` | false | hidden / hidden |
| `https://shop.kind.co.jp/products/8001001141404` | true | possibly_real |

Inserted through `CampaignOrchestrator._publish` + `list_public_results`,
empty URL and `javascript:` produce **zero** public rows.

**Verdict.** Holds. The remaining publish leak is empty `reason_codes` on a
real `https` URL, which is a different claim.

### 3. Generic category profile no longer expects view "unknown"; non-footwear completeness is not pinned at 0.4

**Command.** `verify_claims.check_generic_profile` and
`tests/unit/test_generic_profile_views.py`.

**Result.** `profile_for("garment").expected_views` is
`("front", "rear", "detail", "label")`. `"unknown"` is absent. All four
names are `ViewHypothesis` values. Full coverage scores **1.0**. Empty
coverage scores **0.4** (the critical-view term still defaults to 1.0 when
there are no critical views). Footwear still expects `sole`.

On the live Willy campaign every judged garment had
`evidence_completeness = 0.80`, not 0.40. Authenticity lower bound stayed
**0.40**.

**Verdict.** Holds for completeness. It does not, by itself, lift the
authenticity floor that blocks Real.

### 4. View classification is category-aware: a garment filling the frame reads front, not heel

**Command.** `verify_claims.check_view_classification` and
`tests/unit/test_view_class_by_category.py`.

**Result.** `classify_listing_view` on a product-role subject with
`subject_area=0.64`: garment → `front`; footwear → `heel`; `category=None`
→ `front`. A close crop (`0.12`) of a garment → `detail`.

Live compare payloads on the published shirts still list parts
`eyelets`, `lateral_panels`, `outsole`, `heel`. The classifier is
category-aware; the compare ontology is not.

**Verdict.** The stated classification claim holds. Compare is still a
footwear reading of a shirt.

### 5. A size can no longer become part of a brand; the shop is not asked for `prada-38`

**Command.** `verify_claims.check_size_not_brand` and
`tests/unit/test_size_is_not_a_brand.py`.

**Result.** `parse_user_text("PRADA(プラダ) ハイヒールパンプス ブラック サイズ 38 1/2",
["PRADA"]).brand_tokens == ["PRADA"]`. `query_slugs` of that brand is
`["prada"]`. Compiled query slugs include `prada`, `prada-prada`,
`prada-vintage` — not `prada-38`. The legacy call `query_slugs("PRADA 38")`
still returns `["prada-38"]`, so the leak is closed at parse time, not
inside `query_slugs`.

**Verdict.** Holds on the path that used to emit `prada-38`.

### 6. Index expansion ranks members against the query, including the user's own text and tags, before the cap. Prada at feed position 104 is taken first of 24

**Command.** `verify_claims.check_index_ranks_before_cap`. Source of
`DiscoveryEngine._intent_terms` and `expand_index`. Live KIND expansion.

**Result.** Synthetic Shopify feed of 120 products, Prada at index 103
(position 104), `per_index_cap=24`, query texts = user text + tag `PRADA`:

- ranked: first taken handle `8003001995070`, rank 1 of 24
- unranked (no `query_texts`): first handle `filler-0000`; Prada not in
  the 24

`DiscoveryEngine.run` seeds `_campaign_query_texts` from compiled queries
**and** `_intent_terms` (intent text and tags). Live KIND expansion of
"Willy Chavarria" took `https://shop.kind.co.jp/products/8001001141404`
first of 24 from 224 members.

**Verdict.** Holds.

### 7. Acceptance harness no longer reports behaviour 21 as met; flagship score is 20 of 24, not 21

**Command.** Read `scripts/flagship_acceptance.py`; evaluate the live
Willy campaign with that `evaluate` (stubbing `browser_processes` because
this sandbox cannot run `ps`).

**Stored** `artifacts/searcher-flagship-matched.receipt.json`: met 20,
not met 1, not evaluable 3. Behaviour 21 is `not evaluable`.

**Independent**, this pass's Willy campaign: **met 20, not met 1, not
evaluable 3**. The single `not met` is behaviour 15 (Real=0). Behaviours
2, 5, and 21 are `not evaluable`. Behaviour 21's observation is "this
harness does not interrupt the campaign it scores".

The Dior stored receipt remains met 13 / not met 3 / not evaluable 8.

**Verdict.** 20/24 reproduces on a Willy campaign under their evaluator.
It is not the Bible §40 Dior scenario. Behaviour 22 was scored `met` only
after stubbing `ps`; it was not observed on this host.

### 8. `uv run mypy src` passes on a clean clone without torch installed

**Command.** Fresh `uv run` venv in this worktree, then `uv run mypy src`,
then `importlib.util.find_spec("torch")`.

**Result.** `torch False`. `Success: no issues found in 262 source files`.
Exit 0.

**Verdict.** Holds.

### 9. A replica can no longer reach Real; thirteen phrasings are regression tests

**Command.** Attack A; `tests/unit/test_replica_phrases.py` (`LEAKED` has
13 strings).

**Result.** 13/13 publish as `replica`. A yupoo (replica-family) adapter
with a stored Real decision publishes as `replica`. Reached Real: `[]`.

**Verdict.** Holds.

### 10. Discovery expands listing indexes (18 products / 60 images, not one imageless collection URL)

**Command.** `uv run python artifacts/listing-expansion/run_kind_live.py`

**Result.**

```text
candidates 24
product_urls 24
with_images 24
index_canonical_urls []
members_found 224, taken 24, dropped 200 (per_index_cap)
first URL https://shop.kind.co.jp/products/8001001141404 (5 images)
coverage kind=SEARCHED_MATCHES_FOUND
```

The imageless collection-feed URL is gone on this path. The exact
**18 / 60** counts did not reproduce: the default cap is 24 and the feed
now has 224 members.

**Verdict.** Expansion works. 18/60 is a single earlier run, not an
invariant.

### 11. A live search publishes 5 Possibly Real, true listing first, working link

**Command.** `uv run python artifacts/grading-round3/live_willy_search.py`,
then `curl -sI` on each published URL.

**Result.**

| Field | Observed |
|---|---|
| terminal | `PARTIAL` / `budget exhausted` in 197.25s |
| Possibly Real | **2** (not 5) |
| Real | 0 |
| true listing | `https://shop.kind.co.jp/products/8001001141404` at **rank 1** |
| `listing_url` | present on both |
| HTTP | **200** on both |
| tab_reason | includes `Reason codes: possibly-real-gate.` |
| item_match lower | 0.550 / 0.534 |
| authenticity lower | **0.40** on both |
| completeness | **0.80** on both |

**Verdict.** Rank-1 true listing and working links hold. The count of 5
does not; this run published 2. The previous independent pass published
4. The number is run-dependent.

### 12. COMPLETE now requires that source work actually ran

**Command.** Attack B. Also
`tests/integration/test_terminal_requires_work.py` (inside the 458).

**Result.**

| Case | State | Reason |
|---|---|---|
| empty campaign | `BLOCKED` | no usable query was compiled |
| query compiled, no source work | `BLOCKED` | no source work was planned |
| source marked completed, `pages_fetched=0`, no candidates | `BLOCKED` | nothing was fetched |
| `forced=COMPLETE` override | `COMPLETE` | internal override only |

**Verdict.** Holds on the public path.

### 13. A capability reports available only after a probe that really loads and runs

**Command.** Attack C, before and after installing torch.

**Result.**

| Case | available | notes |
|---|---|---|
| dummy file, no probe | false | `unknown` … `not probed` |
| dummy file, `probe=True` (no torch) | false | torch not importable |
| zero-byte / missing path | false | treated as missing |
| `GET /v1/capabilities` path (`probe_capabilities`) | DENSE_FEATURES false | **does not call `probe=True`** |
| dummy + internal `record_probe_result(True)` | true | cache poison; not a public API |
| real `embedding.pt`, no torch, `probe=True` | false | torch not importable |
| real `embedding.pt` + torch + `probe=True` | **true** | `probe call succeeded; no download performed` |

`NEXT_VIEW` is hard-coded `available=True` without a load/run probe.

**Verdict.** DENSE_FEATURES does not claim available from file existence.
Availability after a real forward pass was confirmed once torch and
weights were present. The HTTP capabilities endpoint never probes.

### 14. Nine documents were corrected; a test fails when docs and code disagree

**Command.** `tests/unit/test_docs_match_capabilities.py` (5 tests, all
passed after receipts were restored). Existence check of the nine files
named in commit `efdd124`.

**Result.** All nine exist. None of the nine forbidden phrases remain.
A simulated revert of `discovery is not wired into that process` into
`ARCHITECTURE.md` would fail the test. The test guards **six** of the
nine files. `README.md`, `docs/OPERATING.md`, and
`docs/architecture/MATCHING_AND_AUTHENTICITY.md` are unguarded.

**Verdict.** Nine documents were corrected. The disagreement test is real
and narrower than the claim.

### 15. Pair threshold is a shortlist cut, not an identity gate; 0.86 admits 70% of different-listing pairs

**Command.** `uv run python -m benchmark.threshold` with DINOv2 weights.
Read `src/searcher/core/embedding_gateway.py` and public docs.

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
`SEARCHER_BUCKET_POLICY.md`, or `README.md`. Those files mention 0.771 /
0.867, which is not the 0.86 operating point.

Without weights the same command reports shipped FPR **0.0** on the cheap
scorer — the 70% number is DINOv2-specific.

**Verdict.** The measurement holds. The public-doc half of the claim is
still only a code comment.

### 16. Fast suite 52s; live campaign ~130s

**Command.** Timed `./scripts/test_all.sh`.

**Result.** 51.28s and 132.17s. Same order of magnitude as the quoted
numbers; this host was slightly faster on the fast suite and slightly
slower on the live campaign than the quoted figures.

---

## Four attacks

Recorded in `artifacts/grading-round3/attacks.json`.

### Attack A — publish a replica to Real

Attempted with the 13 + 30 committed phrases plus 19 extra seller
phrasings, all given perfect match and authenticity scores under
`matching-1`.

- **13/13 + 30/30 committed phrases:** published `replica`, never Real,
  never Possibly Real.
- **Replica-family source** with a stored Real decision: published
  `replica`.
- **Reached Real: []**.
- Extra phrases that still published **Possibly Real**: `not legit`,
  `this is not legit`, `god batch`, `retail batch`, `rep1ica`,
  `repliсa` (Cyrillic `с`), `dup`.
- `Copy of the original receipt included` also published Possibly Real
  — that is the intended non-replica reading, not a leak.
- Clean listings (`faux fur`, `fake leather`, `Authentic Prada`) were
  not flagged.

**Outcome.** Failed to reach Real. Succeeded in putting undeclared
replica language (`not legit`, homoglyph `repliсa`) on the Possibly
Real tab, which `SEARCHER_BUCKET_POLICY.md` forbids ("A replica listing
can never be ranked Real or Possibly Real").

### Attack B — reach COMPLETE without fetching

Empty campaign, compiled-query/no-source, and
`sources_completed` + `pages_fetched=0` all returned `BLOCKED` with a
named reason. Only `forced=COMPLETE` produced COMPLETE.

**Outcome.** Blocked on the public path.

### Attack C — make a capability lie

A dummy or empty weights file never produced `available=True` through
`embedding_capability` or `probe_capabilities`. Unprobed files report
`unknown`, not available. A real weights file plus `probe=True` reported
available only after torch was present and a forward pass ran.

**Outcome.** Blocked for DENSE_FEATURES. `NEXT_VIEW` is advertised
available without a probe (different capability). The HTTP
`/v1/capabilities` path never probes.

### Attack D — publish a result without a reason or a link

| Case | Public rows | listing_url | reason codes |
|---|---:|---|---|
| empty canonical_url + empty reason_codes | 0 | — | — |
| `javascript:alert(1)` | 0 | — | — |
| https URL + empty reason_codes | **1 Possibly Real** | present | **absent** |
| routed honest listing | 1 | present | present |

**Outcome.** The link leak found on `a7a5a98` is closed. A result with
no reason codes still publishes if the URL is usable. Not the default
router.

---

## Receipt comparisons

Canonical cited receipts were restored after comparison so `CLAIMS.md` /
the docs test still match the DINOv2 figures. Copies live under
`artifacts/grading-round3/receipts-before/` and
`artifacts/grading-round3/receipts-after/`.

### `searcher-public-benchmark.receipt.json`

| | Stored | Regen, no weights | Regen, DINOv2 |
|---|---|---|---|
| SHA-256 (prefix) | `2c6701abf8f8…` | `27cfbeaa143a…` | `966839b6d48b…` |
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
| cold campaign_wall_ms | 49.069 | 49.63 |
| warm campaign_wall_ms | 29.266 | 31.183 |
| warm cache_hit_rate | 1.0 | **1.0** |
| duplicate_work_avoided | 1.0 | **1.0** |
| cold candidates / results | 5 / 5 | 5 / 5 |

Shape holds. Timings moved a few milliseconds on this host.

---

## What would raise each score below 90

**Plan fidelity (78).** Run the Bible §40 Dior input to a campaign that
satisfies behaviour 15 (a Real result earned by evidence, not a lowered
gate). Stop scoring a substituted Willy item as the flagship. Emit the
§39 files under the names the Bible lists, or amend the Bible.

**Implementation completeness (80).** Same Real result. Stop reporting
eyelets / outsole / heel on a shirt. Either admit Grailed / Vestiaire /
Depop under a real policy or keep them disabled (already honest) and
stop counting them as missing coverage.

**Real-runtime proof (77).** Flip soak/abuse to `SEARCHER_LIVE_DISCOVERY=1`
and stop asserting `BLOCKED` as the only honest soak outcome. Re-run the
21-case adversarial-recall receipt against the expanded discovery path
and get a non-zero recall.

**User-visible proof (84).** Make `_publish` refuse a public bucket when
`reason_codes` is empty. Expose crops and hypotheses so behaviours 2 and
5 are evaluable. Put one result in Real.

**Retrieval quality (73).** A pair threshold that holds on held-out data
at the 5% FPR ceiling, on a labelled set larger than 10+10. Report
Real-tab precision once anything is in Real. Move adversarial recall off
0/21.

**Authenticity safety (88).** Treat `not legit`, `god batch`, leetspeak
(`rep1ica`), and Cyrillic-homoglyph `repliсa` as replica language; add
them to the regression list. Field-calibrate authenticity so the
interval is not stuck at 0.40 on a garment whose completeness is 0.80.

**Security and privacy (83).** Rewrite history so
`./scripts/scrub_public_tree.sh` is clean with
`SEARCHER_SCRUB_FAIL_ON_HISTORY=1`. Run soak/abuse against live
discovery. Authentication if this process is ever shared beyond a
single operator.

**Cost efficiency (81).** A live cost ledger with cache-hit rate and a
first-published-result time that is not "budget exhausted after 197s".

**Test quality (85).** Add tests for residual replica slang and for "no
public row without a reason". Stop asserting soak `BLOCKED` while
claiming live discovery is the default. Guard the three unguarded
documents.

**Documentation (80).** Put "shortlist cut, not an identity gate" and
the 70% held-out FPR in `CLAIMS.md` / `LIMITATIONS.md` next to 0.86.
Cite the scorer identity next to 0.771 so a no-weights `benchmark --all`
cannot silently retitle the receipt. Replace "generic empty profile" in
LIMITATIONS. Add the missing §39 filenames.

---

## §39 terminal status

**NOT_READY.**

Required named deliverables that are absent under the Bible names (some
exist under other paths; that is not the list in §39):

- `SEARCHER_SOURCE_AUTHORITY.md`, `SEARCHER_REUSE_LEDGER.json`,
  `SEARCHER_ARCHITECTURE.md`, `SEARCHER_DATA_MODEL.md`,
  `SEARCHER_UX_SPEC.md`, `SEARCHER_PERFORMANCE_BASELINE.md`,
  `SEARCHER_RELEASE_READINESS.md`, `SEARCHER_TERMINAL_REPORT.md`
- `SEARCHER_SOURCE_POLICY.md`, `SEARCHER_SECURITY.md`,
  `SEARCHER_PRIVACY.md`, `SEARCHER_BENCHMARK_METHOD.md`,
  `SEARCHER_PUBLIC_BENCHMARK_REPORT.md`, `SEARCHER_LIMITATIONS.md`
- `artifacts/searcher-clean-clone.receipt.json`,
  `artifacts/searcher-security.receipt.json`,
  `artifacts/searcher-terminal.receipt.json`

Present under the Bible name:
`SEARCHER_AUTHENTICITY_POLICY.md`, `SEARCHER_BUCKET_POLICY.md`,
`SEARCHER_FINAL_SCORECARD.md`,
`artifacts/searcher-performance.receipt.json`,
`artifacts/searcher-public-benchmark.receipt.json`.

Present under close names: `ARCHITECTURE.md`, `SOURCE_POLICY.md`,
`SECURITY.md`, `PRIVACY.md`, `LIMITATIONS.md`,
`docs/SEARCHER_BENCHMARK_METHOD.md`,
`docs/SEARCHER_PUBLIC_BENCHMARK_REPORT.md`, plus several audit receipts
under `artifacts/audit/`.

### Smallest set that would clear NOT_READY

In order, because §38.2 does not average:

1. **Close residual replica language** so a listing that says `not legit`
   / `repliсa` (homoglyph) cannot land on Possibly Real, and lock it
   with tests. (Authenticity safety → 90.)
2. **Earn one Real** on an authorized item that actually has the views
   the gate demands — and stop judging a shirt with a shoe's parts — or
   amend §40.15. Without behaviour 15, plan fidelity and implementation
   completeness cannot reach 90 against this Bible.
3. **Soak with live discovery + reason-code publish test + residual
   slang tests.** (Test quality and real-runtime proof.)
4. **History rewrite** so the public-tree scrub is clean.
5. **Write the missing §39 terminal files** from evidence that already
   exists.

Item 2 is the hard blocker. This tree is willing to say "nothing reaches
Real" and that is currently true: live garments now reach completeness
0.80 and still sit at authenticity lower bound 0.40 because label, logo,
and provenance are missing. The Bible still requires high-evidence
candidates in Real for the flagship. Until that happens, or the Bible is
amended, the terminal status stays NOT_READY.

---

## Defects this pass opened (not in the admitted list)

- Residual replica slang (`not legit`, `god batch`, homoglyph
  `repliсa`, `dup`) still reaches Possibly Real.
- `_publish` will place a Possibly Real row with no reason codes if the
  URL is a usable `http(s)` link.
- Live compare still reports footwear parts (eyelets, outsole, heel) on
  a long-sleeve shirt.
- Live authenticity lower bound is still 0.40 on garments whose
  completeness is 0.80.
- `uv run python -m benchmark --all` without weights overwrites the
  cited public receipt and would fail the docs test; it also rewrites
  two committed hard-negative PNGs.
- Soak and abuse still set `SEARCHER_LIVE_DISCOVERY=0` and assert
  `BLOCKED`.
- `GET /v1/capabilities` never probes DENSE_FEATURES.
- `NEXT_VIEW` is advertised available without a probe.
- Stored adversarial-recall receipt is still 0/21 (not re-run this
  pass; the file on disk is the claim).
- LIMITATIONS still describes the generic profile as empty.

Admitted weaknesses confirmed, not rediscovered: nothing reaches Real;
Grailed / Vestiaire / Depop stay out; the backbone bake-off that chose
DINOv2 is not in this tree. The DINOv2 **receipts** do reproduce when
the operator's weights file is pointed at.

---

## Evidence index

| Path | What |
|---|---|
| `artifacts/grading-round3/attacks.json` | Four attacks |
| `artifacts/grading-round3/verify_claims.json` | Independent claim checks |
| `artifacts/grading-round3/scores.json` | This pass's scores |
| `artifacts/grading-round3/live-kind.json` | Live KIND expansion |
| `artifacts/grading-round3/live-willy.json` | Independent live search |
| `artifacts/grading-round3/live-willy-projected.json` | Projected reasons/links |
| `artifacts/grading-round3/live-willy-flagship.json` | Independent 20/24 evaluation |
| `artifacts/grading-round3/receipts-before/` | Snapshots of cited receipts |
| `artifacts/grading-round3/receipts-after/noweights/` | Cheap-scorer regenerations |
| `artifacts/grading-round3/receipts-after/dinov2/` | DINOv2 regenerations |
| `artifacts/grading-round3/searcher-performance.regen.json` | Performance regeneration |
| `artifacts/grading-round3/test_all.log` | Timed full suite |
| `artifacts/grading-round3/benchmark-all-noweights.log` | No-weights `--all` |
| `artifacts/grading-round3/benchmark-all-dinov2.log` | DINOv2 `--all` |
| `artifacts/grading-round3/benchmark-threshold-noweights.log` | No-weights threshold |
| `artifacts/grading-round3/benchmark-threshold-dinov2.log` | DINOv2 threshold |
| `artifacts/grading-round3/mypy.log` | mypy without torch |
| `artifacts/grading-round3/ruff.log` | ruff |
| `artifacts/grading-round3/scrub.log` | Scrub output |
