# Searcher terminal report

Bible §39. Bound to git SHA
`31e6004c76e1d845447e0993a5ce68948f311265`. Host `Mac-Studio`.
Date 2026-08-17. Receipt: `artifacts/searcher-terminal.receipt.json`.

Terminal status: **NOT_READY**

## Repository

Searcher, version `0.1.0` (`pyproject.toml`). Public clone URL
documented in `README.md`:
`https://github.com/joshuahickscorp/searcher.git`. There is no
hosted API. The published page
`https://joshuahickscorp.github.io/searcher/` is static files from
`web/`.

## Branch

This worktree branch is `grok/searcher-terminal2-20260817-002547`.
The named commit is `31e6004c76e1d845447e0993a5ce68948f311265`
(`git rev-parse HEAD`), message “Plan the sources from the
registry, not from a list typed by hand”.

## Exact SHA

`31e6004c76e1d845447e0993a5ce68948f311265`

## Donor repositories and SHAs

| Donor | SHA / identity | Evidence |
|---|---|---|
| VisionMCP | `18ee3c06d27f04937d1681dea5fa2650131e4b2a` (`visionmcp-ocular` 0.8.0a2, tag `v0.8.0-alpha.2`) | `docs/audit/SOURCE_AUTHORITY.md`, `artifacts/audit/source-authority.json` |
| Job Scraper | no git SHA. Frozen snapshot manifest digest `3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2` | `docs/audit/JOB_SCRAPER_CAPABILITY_HARVEST.md`, `src/searcher/sources/adapters/__init__.py` |
| MTP | none. Absent on the 2026-08-16 locate | `docs/audit/MTP_CAPABILITY_HARVEST.md` |

Donor locate was not re-run at this SHA. See
`SEARCHER_SOURCE_AUTHORITY.md`.

## Adopted VisionMCP capabilities

From `SEARCHER_REUSE_LEDGER.json` (56 entries; counts DEFER 11,
PORT_MINIMAL_COMPONENT 1, REIMPLEMENT_FROM_CONTRACT 3, REJECT 15,
REUSE_AS_PACKAGE 1, WRAP_WITH_ADAPTER 25).

**REUSE_AS_PACKAGE:** `visionmcp-ocular` 0.8.0a2.

**WRAP_WITH_ADAPTER** (in-process, lazy): capability report, core
doctor, public API versions, CORE_TOOLS, ProjectStore,
ArtifactStore, receipt verify, inspect_image, ImageFileAdapter,
analyze_image, CaptureBus, silhouette compare, browser capture and
browser_slot, WorldMemory / merge_identities, AcquisitionOS /
SearchExhaustionReceipt / SearchSource, PluginRegistry, public
CLI, lazy_optional, require_imaging, confined_path.

**PORT_MINIMAL_COMPONENT:** `NextViewRequest` field set only.

Primary integration path: in-process core adapter. Fallback: CLI
subprocess. Missing capability → structured unavailable, campaign
continues.

## Adopted Job Scraper capabilities

Not a package pin. Honest primitives reimplemented from the frozen
snapshot: per-host pacing, robots cache, retry ceiling, circuit
breaker, work key, fetch log, live-status classification
(`ARCHITECTURE.md`, harvest §7). Searcher-owned adapter wraps the
ports, not the donor process.

## Adopted MTP capabilities

None. MTP is absent. Searcher's campaign controller covers Bible
§7.

## Rejected donor components

VisionMCP: search/greed MCP profiles as a crawler; synthetic
feature-ID detector; visual compiler; Blender; Ghidra; COLMAP;
Studio as Searcher UI; organic/fur; source-code repair;
generative weights.

Job Scraper §6.10: UA rotation, TLS impersonation (`curl_cffi`),
proxy pools, stealth Playwright, persistent browser profiles,
fingerprint diversification, human-pause. Also rejected: internship
ranking, ATS fetchers, dashboard/CRM.

Evidence: `SEARCHER_REUSE_LEDGER.json`,
`tests/unit/test_donor_rejection.py`.

## Test counts

Command: `./scripts/test_all.sh`.

This session, SHA `31e6004`, host `Mac-Studio`:

```text
14 failed, 492 passed, 7 skipped, 1 deselected, 26 errors in 742.13s
exit 1
```

Collected: 540 tests (539 plus 1 `live_campaign`). By folder, on
`uv run pytest --collect-only -q`: unit 381, integration 47,
property 41, real_runtime 35, security 27, adversarial 5,
metamorphic 3.

The live-campaign invocation inside `test_all.sh` did not run:
the wrapper is `set -e` and the first pytest exited 1.

Failures and errors were subprocess spawn `SIGSEGV` (-11) after
tesseract OCR (`src/searcher/reference/ocr.py:run_tesseract`) and
on later child `python` / `bash` invocations (`test_first_run`,
`test_serve_shared`, `test_probe_and_import`, abuse/soak API
processes, crash-resume migrate). That is this environment losing
the ability to spawn children mid-suite, the condition
`scripts/test_all.sh` already documents for the live-campaign
split. It is not a new product assertion.

Last committed green run, `artifacts/grading-round3/test_all.log`,
commit `6435d24`:

```text
458 passed, 6 skipped, 1 deselected in 51.28s
1 passed, 464 deselected in 132.17s
exit 0
```

SHA `31e6004` has more tests than `6435d24` (540 collected vs the
458+1 of that log). A green full-suite number at this SHA is not
established in this session.

`uv run ruff check .`: All checks passed.

`uv run mypy src`: exit 1. One unused `type: ignore` at
`src/searcher/matching/features.py:44`. 269 source files checked.
Pre-existing at this SHA. This session did not edit `src/`.

## Coverage

Unknown. `pyproject.toml` does not declare `pytest-cov` or a
coverage tool. Bible §32.1 floors (critical-path statement ≥ 90%,
branch ≥ 80%) are not measured.

## Real-runtime tests

Files under `tests/real_runtime/`:

- `test_api_abuse.py`
- `test_api_soak.py`
- `test_browser_close_on_raise.py`
- `test_browser_leak.py`
- `test_crash_resume.py`
- `test_frontier_sigkill.py`
- `test_orchestrator_live.py` (marker `live_campaign`)
- `test_orchestrator_sigkill.py`
- `test_real_network.py`

35 collected. This session: several failed or errored because
child processes exited -11; `test_real_network_admitted_sources`
timed out at 240s. The live-campaign test was not invoked.

Last committed green live-campaign result: 1 passed in 132.17s
(`artifacts/grading-round3/test_all.log`).

Soak and abuse still set `SEARCHER_LIVE_DISCOVERY=0` and assert
`BLOCKED` (`docs/grading/ROUND_2.md`).

## Benchmark metrics

Cited receipt, DINOv2, command
`uv run python -m benchmark.run --all`,
`artifacts/searcher-public-benchmark.receipt.json` (git
`28c2eb6bc5fba57fd4d5a9946c45243a265adcd3`):

| metric | value |
|---|---|
| n | 35 |
| recall@1 | 0.771429 |
| recall@5 | 1.0 |
| recall@10 | 1.0 |
| MRR | 0.866667 |
| false Real | 0 |

This session, same command, no local weights, scorer
`searcher.cheap_visual.ahash_colour`, git
`31e6004c76e1d845447e0993a5ce68948f311265`:

| metric | value |
|---|---|
| n | 35 |
| recall@1 | 0.914286 |
| recall@5 | 1.0 |
| recall@10 | 1.0 |
| MRR | 0.940476 |
| false Real | 0 |

Saved as `artifacts/searcher-public-benchmark.noweights.receipt.json`.
The §39 path was restored to the committed DINOv2 receipt so
`CLAIMS.md` and `tests/unit/test_docs_match_capabilities.py`
remain consistent.

OpenCV is not importable in this session
(`opencv_available() is False`). Correspondence TPR 1.000 / FPR
0.000 is the committed measurement in
`src/searcher/matching/correspondence.py` on
`fixtures/user_snapshots`. The test that would remeasure is
skipped without opencv.

## Real precision

On the constructed 7-case bucket protocol in the public-benchmark
receipt: Real precision 1.0 (1 / 1). That is not a live
authenticity-accuracy number.

On live campaigns in this tree, Real count is 0
(`artifacts/searcher-flagship-matched.receipt.json`,
`artifacts/realmatch/results.json`,
`artifacts/operator/search-results.json`). Live Real precision is
not established: the denominator is empty.

## Combined recall

Not computed as a named live metric. Bible §31.7 target
“combined Real + Possible displayed recall ≥ 95%” has no live
receipt. Fixture-protocol recall for the four constructed labels
is 1.0 each. Retrieval recall@5 on the 35-query held-out set is
1.0 (both scorers).

## Counterfeit / mismatch leakage

Fixture protocol: false Real 0; hard-negative cases
`adjacent_model`, `different_colourway`, `stolen_photos`,
`replica_copied_title` routed hidden or replica
(`artifacts/searcher-public-benchmark.receipt.json` `buckets.rows`).

Live: committed replica phrase lists (13 + 30) publish as
`replica`, never Real (`docs/grading/ROUND_2.md` Attack A).
Residual slang (`not legit`, `god batch`, homoglyph `repliсa`,
`dup`) still reached Possibly Real at commit `6435d24`. That
leakage into Possibly Real is forbidden by
`SEARCHER_BUCKET_POLICY.md`. It has not been re-attacked at
`31e6004`.

## Source coverage

Ten admitted, enabled, credential-free sources, derived from the
registry, command:

```text
uv run python -c "from searcher.workers.api_campaign import uncredentialed_source_names; print(uncredentialed_source_names())"
```

Result this session: `searx`, `wikimedia`, `marginalia`,
`the_realreal`, `rebag`, `komehyo`, `kind`, `byronesque`,
`heroine`, `archive_org`.

No API key, developer account, or marketplace agreement is used
on that plan. eBay and Etsy require keys and are omitted.

A given live campaign does not necessarily complete all ten.
Flagship receipt coverage completed `kind` and `heroine` and
blocked others. Commit `31e6004` records that Rebag can be in the
plan and still not attempted.

## Blocked sources

Stay disabled, `review_required`:

| Source | Reason |
|---|---|
| Grailed | Cloudflare challenge on listing pages |
| Vestiaire | HTTP robots and listings challenged |
| Taobao | item URLs typically Disallow |
| Weidian | no fetchable robots file (redirect to 404) |
| Yupoo | no fetchable robots file |
| Depop | plain HTTP 403 / challenge |

Plus the rest of the `review_required` set in `SOURCE_POLICY.md`
(Vinted, Mercari JP, Yahoo Auctions, Buyee, Bunjang, SSENSE,
Farfetch, StockX, GOAT, Poshmark, DuckDuckGo HTML). DHgate is out
of scope.

## Model calls

Zero on the search path. Fixture campaigns record
`model_calls: 0` (`artifacts/searcher-performance.receipt.json`).
Live runners set `model_call_limit=0`. The only learned component
is a local DINOv2 ViT-S/14 loaded from a traced file. A search
never downloads weights. This session had no local weights.

## Cost

No monetary ledger. Operational cost on the offline public
benchmark: fetches_per_campaign 0, cache_hit_rate 1.0,
images_per_second 82.245 (committed receipt). Live campaign cost
is wall time and fetches, not dollars. Unknown as a currency
figure.

## Performance

`artifacts/searcher-speed.receipt.json`, three live runs each:

- before median 199474.107 ms (runs 199474.107, 203276.165,
  197236.244)
- after median 95704.578 ms (runs 99032.254, 95704.578,
  86524.518)

Fixture warm cache-hit 1.0, duplicate_work_avoided 1.0
(`artifacts/searcher-performance.receipt.json`). Engineering
targets are in `SEARCHER_PERFORMANCE_BASELINE.md`. Time to first
Real: not established (Real count is 0).

## Privacy

Local engine. Uploads stay on the operator machine. No training,
no telemetry, no third-party model upload. Delete returns 204 and
subsequent reads are 404. See `SEARCHER_PRIVACY.md`.

## Security

SSRF allowlist, upload caps, prompt-injection contract,
cross-campaign isolation, honest User-Agent, no stealth.
Security-related suite this session: 49 passed in 2.18s
(`artifacts/searcher-security.receipt.json`). Full §29.4 browser
sandbox is partial. No hosted auth.

`./scripts/scrub_public_tree.sh` exits 1 on this working tree
(360 findings). All of those findings are in files already
committed at this SHA (`artifacts/grading-round3/`,
`artifacts/searcher-speed.receipt.json`, and
`src/searcher/sources/platform.py`). New §39 files add none.
History is also dirty. See `SEARCHER_SECURITY.md`.

## Known limitations

See `SEARCHER_LIMITATIONS.md`. The ones that decide status:

- Nothing published reaches Real. Gate `item_match >= 0.90` versus
  genuine-pair median 0.8101 and TPR 0.237 at 0.90
  (`artifacts/searcher-match-calibration.receipt.json`). Live
  authenticity lower bound on garments has been 0.40.
  Destination verification of kind.co.jp has answered with a
  challenge (`tests/unit/test_verification.py`).
- Shipped pair threshold 0.86 admits 70% of different-listing
  pairs (`artifacts/searcher-threshold.receipt.json`). Shortlist
  cut, not an identity gate.
- §40 flagship: 20 met, 1 not met (behaviour 15, Real), 3 not
  evaluable (`artifacts/searcher-flagship-matched.receipt.json`).
  Input was a Willy Chavarria garment, not the Bible's Dior
  trainer.
- Last independent §38 grades, commit `6435d24`, all below 90
  (`docs/grading/ROUND_2.md`, `SEARCHER_FINAL_SCORECARD.md`).
- Correspondence without opencv is noise. opencv was False here.
- Four footwear-shaped paths asked a garment for its sole. Later
  commits changed those paths; a fresh live compare at this SHA
  is not in the tree.
- Unequal label-region perceptual hashes are no longer a hard
  product-code contradiction (`f6ecd58`).
- Residual replica slang reached Possibly Real at `6435d24`.

### Facts this report must not over-claim

The published page exists. `artifacts/operator/RECEIPT.md`
recorded `GET https://joshuahickscorp.github.io/searcher/` → 200
(10826 bytes) and `/v1/health` on that origin → 404. Tunnel
sharing is documented in `docs/OPERATING.md`. A committed
campaign receipt of a stranger search through that public URL
that returned three `shop.rebag.com` results is **not in this
tree**. Live Rebag catalogue reach is tested in
`tests/integration/test_second_shop_live.py`. Rebag is one of the
ten uncredentialed planned sources.

## Exact public claim ceiling

Searcher is entitled to say only what `CLAIMS.md` lists as
Entitled, each with its evidence pointer. In one paragraph:

Searcher accepts images, text, and tags as a search intent and
treats user text as a hypothesis. Uploads are validated by magic
bytes; EXIF is quarantined after orientation. It compiles
alternate names and multilingual query families from the
hypothesis portfolio. Campaign state persists in SQLite WAL and
can be reconstructed after interruption. `ITEM_MATCH`,
`AUTHENTICITY_CONFIDENCE`, and `LISTING_UTILITY` are separately
typed; public gates read lower bounds. Matching uses classical
descriptors and a local DINOv2 ViT-S/14 when a real probe of a
local traced file succeeds; a search never downloads weights.
Users see Real and Possibly Real; hard vetoes bar both; there is
no public Fake tab. Uncalibrated authenticity is incomplete
evidence and cannot pass Real under `matching-1`. Outbound
fetches allow only `http`/`https` and refuse private/metadata
destinations. Listing text and pixels that look like instructions
are data. Campaigns are isolated. Deletion removes private
artifacts; receipts remain. Adapters expose a manifest;
`review_required` adapters ship disabled. Receipts are
hash-chained. The served API does not invent a successful empty
search. The Job Scraper evasion surface is not present. There is
no hosted API. A declared public benchmark exists: recall@1
0.771, recall@5 1.0, MRR 0.867 over 35 queries, false Real 0, on
the DINOv2 receipt, not an authenticity-accuracy claim.

It is **not** entitled to say that a finished live search will
produce a Real result; that the pair threshold is an identity
gate; that it is a professional authenticator; that it covers
every marketplace; that it is better than conventional image
search; that a blocked source contained no result; that a
marketplace badge makes a listing authentic; that international
adapters are approved; or any number that is not in a named
receipt.

## Launch status

**NOT_READY**

The Bible allows exactly one of `PRIVATE_ALPHA_READY`,
`PUBLIC_ALPHA_READY`, `PARTIAL_WITH_BLOCKERS`, `NOT_READY`.

`PRIVATE_ALPHA_READY` and `PUBLIC_ALPHA_READY` would require the
§38.2 floors and a Real result the evidence does not have.

`PARTIAL_WITH_BLOCKERS` would be a fair description of a working
search that returns Possibly Real listings on admitted sources.
That search exists. The Bible's completion bar does not: no
critical dimension reached 90 on the last independent pass; §40
behaviour 15 is not met; nothing publishes to Real; residual
replica slang still reached Possibly Real at that pass; this
session's required suite did not finish green.

The honest launch status is **NOT_READY**.

## §39 path inventory

| Path | Status |
|---|---|
| `SEARCHER_SOURCE_AUTHORITY.md` | written this session |
| `SEARCHER_REUSE_LEDGER.json` | bound this session from `artifacts/audit/reuse-ledger.json` |
| `SEARCHER_ARCHITECTURE.md` | written this session |
| `SEARCHER_DATA_MODEL.md` | written this session |
| `SEARCHER_SOURCE_POLICY.md` | written this session |
| `SEARCHER_AUTHENTICITY_POLICY.md` | already present |
| `SEARCHER_BUCKET_POLICY.md` | already present |
| `SEARCHER_UX_SPEC.md` | written this session |
| `SEARCHER_SECURITY.md` | written this session |
| `SEARCHER_PRIVACY.md` | written this session |
| `SEARCHER_PERFORMANCE_BASELINE.md` | written this session |
| `SEARCHER_BENCHMARK_METHOD.md` | written this session |
| `SEARCHER_PUBLIC_BENCHMARK_REPORT.md` | written this session |
| `SEARCHER_LIMITATIONS.md` | written this session |
| `SEARCHER_RELEASE_READINESS.md` | written this session |
| `SEARCHER_FINAL_SCORECARD.md` | updated this session with Round 2 |
| `SEARCHER_TERMINAL_REPORT.md` | this file |
| `artifacts/searcher-source-authority.receipt.json` | written this session |
| `artifacts/searcher-reuse-ledger.receipt.json` | written this session |
| `artifacts/searcher-clean-clone.receipt.json` | written this session; not regenerated |
| `artifacts/searcher-security.receipt.json` | written this session |
| `artifacts/searcher-performance.receipt.json` | already present |
| `artifacts/searcher-public-benchmark.receipt.json` | already present (DINOv2); session no-weights copy beside it |
| `artifacts/searcher-terminal.receipt.json` | written with this file |

## Sections written as not established

| Topic | Why |
|---|---|
| Statement/branch coverage | No coverage tool in `pyproject.toml` |
| Dollar cost | No monetary ledger |
| Live Real precision | Live Real count is 0 |
| Combined displayed recall (live) | No named receipt |
| Conventional-search comparison | Bible §31.8 not run |
| Hidden evaluation | No authorized hidden split |
| Authenticity field calibration | Fixture records `not_field_calibrated: true` |
| Mutation tests (Bible §32.9) | No mutation receipt |
| MTP capabilities | Donor absent |
| DINOv2 vs ResNet50 bake-off | Calibration receipt `reproducibility.status` is NOT reproducible |
| Clean clone at this SHA | Not run; last operator clone is `a66414e` |
| Independent §38 regrade of `31e6004` | Last pass graded `6435d24` |
| Stranger public-URL search returning three Rebag results | No committed campaign receipt of that search |
| Time to first Real | Real never published |
| Fresh live garment compare at this SHA | Not in the tree |
| Residual slang closed at this SHA | Not re-attacked |
| Green `./scripts/test_all.sh` at this SHA | This session exit 1, spawn SIGSEGV |
| `uv run mypy src` clean | One unused type ignore, pre-existing |
