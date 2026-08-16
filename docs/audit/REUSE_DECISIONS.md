# Searcher Phase Zero — Reuse Decisions

Inspection date (UTC): 2026-08-16T04:48:46Z  
VisionMCP authority: SHA `18ee3c06d27f04937d1681dea5fa2650131e4b2a`
(`visionmcp-ocular` `0.8.0a2`, tag `v0.8.0-alpha.2`)  
Job Scraper: Desktop tree, **no git**  
MTP: **absent**

Adoption values are exactly the Bible §4.7 enum.

---

## 1. Primary integration path (required)

**Primary: WRAP_WITH_ADAPTER around an in-process import of the
`visionmcp` core control plane, pinned to git SHA `18ee3c06`.**

Concrete shape (later task implements; this task only decides):

```text
src/searcher/integrations/visionmcp/
    adapter lazily imports:
        visionmcp.capabilities.capabilities_report
        visionmcp.capabilities.core_doctor_report
        visionmcp.projects.store.ProjectStore
        visionmcp.artifacts.store.ArtifactStore
        visionmcp.core.imaging          # lazy numpy/Pillow
        visionmcp.perception.media      # ImageFileAdapter, analyze_image
        visionmcp.evidence.references   # inspect_image
        visionmcp.receipts.public       # verify_any_receipt (may need kernels)
        visionmcp.comparison.images     # silhouette only, optional
        visionmcp.perception.browser    # only if web extra + policy
    adapter never imports at module load:
        visionmcp.ocular, blender, binary, compiler, torch, cv2, playwright
```

Install pin (later):

```text
visionmcp-ocular==0.8.0a2 @ git+https://github.com/joshuahickscorp/visionmcp@18ee3c06d27f04937d1681dea5fa2650131e4b2a
# extras: none for API health; [imaging] for observe; [web] for listing capture
```

Distribution is **not** claimed on public PyPI (`README.md`). Pin the
git SHA, not a floating tag.

### Why this path is the most stable

| Surface | Stability at this SHA | Fit for Searcher |
| --- | --- | --- |
| Core Python control plane (`capabilities`, `projects`, `artifacts`, `profiles`, `api`) | Intended public ABI; `visionmcp.api` versions `tools/v1`, `resource/v1`, `receipt/v1` | High — library calls inside a campaign loop |
| Public CLI `visionmcp` (`cli/public.py`) | Curated; `visionmcp-dev` is the churny one | High as fallback |
| MCP core 15 tools | Frozen names in `CORE_TOOLS` + `public-alpha-source-authority.json` | Medium — extra process; `vision.compare` is digest-only |
| MCP search/greed/dev | `search` **not** in `PUBLIC_PROFILES`; tools register caller records | Low — not a marketplace crawler |
| Kernels wheel (`ocular`, `compiler`, `blender`, …) | Explicitly unstable / experimental | Low for MVP |

Heavy dependencies stay off the API health path because core
`[project].dependencies` is empty and
`CORE_FORBIDDEN_MODULES` bans cv2/playwright/torch/… on core import.
Searcher must still **lazy-import** imaging and must not import
`visionmcp.receipts.public` at adapter load (it eagerly imports
`visionmcp.compiler.service`, a kernels module).

### Fallback

**Subprocess CLI** `visionmcp doctor --core`,
`visionmcp capabilities --json`, `visionmcp receipt verify`,
`visionmcp artifact verify`. Used when the in-process import fails
(missing extra, version skew) or when Searcher wants process isolation
without speaking MCP.

MCP `visionmcp serve --profile core` (stdio only) is a **third**
option for isolation, not the default.

### When a capability is missing

The adapter returns a structured `{status: unavailable|blocked|experimental,
reason, remediation}` — the same honesty as
`capabilities_report` — and Searcher continues. Searcher **never**
fabricates embeddings, part matches, authenticity, or "source was
empty" when the source was blocked.

---

## 2. Decision table

### 2.1 Vehicle

| Component | Decision | Reason |
| --- | --- | --- |
| `visionmcp-ocular` 0.8.0a2 @ `18ee3c06` | **REUSE_AS_PACKAGE** | Installable distribution; Searcher does not vendor source |
| `visionmcp-ocular-kernels` | **DEFER** | Required only for compiler/ocular/blender/worlds. MVP must not import it at health-check time |
| VisionMCP MCP server as product bus | **DEFER** | Isolation option only |
| VisionMCP Studio | **REJECT** | Wrong UI; loopback evidence IDE |
| Job Scraper package | **REIMPLEMENT_FROM_CONTRACT** | No SHA; wrong domain; §6.10 mix-in |
| MTP | **DEFER** (absent) | Searcher campaign controller covers §7 |

### 2.2 Bible §5.1–§5.14

| § | Need | What exists at `18ee3c06` | Evidence quality | Decision |
| --- | --- | --- | --- | --- |
| 5.1 | Evidence / artifact spine | `artifacts.store.ArtifactStore`; `projects.store.ProjectStore`; `receipts.public.verify_any_receipt`; `evidence_graph.EvidenceGraph`; `evidence.references.ReferenceIngestor` | Tests exist (`test_profiles_and_plugins`, `test_public_resources`, `test_evidence_graph`). Receipts in `artifacts/release/` bind **older** SHAs. | **WRAP_WITH_ADAPTER** (store + receipts). Searcher owns campaign records. |
| 5.2 | Image calibration | `evidence.references.inspect_image` (EXIF, ICC, orientation, blur/exposure); `perception.media.analyze_image` / `ImageFileAdapter` | Code observed; needs `imaging` (+ cv2 for analyze). Tests not run. | **WRAP_WITH_ADAPTER** (lazy imaging) |
| 5.3 | Attention / foveal crops | `ocular.gaze`, `ocular.retina`, `ocular.proposals`; `active_perception.planner` | Ocular **experimental**; ledger cites missing `artifacts/ocular/honest-baseline/`. Planner is 3D underside-oriented, kernels wheel. | **DEFER** ocular. Searcher implements cheap crop policy itself. |
| 5.4 | Segmentation | `ocular.segment` (classical GrabCut/watershed, `SENSOR_DERIVED`); `features.detector.detect_label_mask` (synthetic RGB IDs); `comparison.images.silhouette_mask` | Classical only; no product-part model. Features detector is fixture-only. | **DEFER** ocular.segment. **REJECT** synthetic detector as a product segmenter. Silhouette: wrap as cheap prefilter only. |
| 5.5 | Dense features / correspondence | `ocular.proposals.propose_dense_features` — Canny + Lab/HOG/moments, **no learned backbone**; core `vision.compare` is **digest identity**; `comparison.images.compare_pair` is silhouette IoU for render-vs-reference | Not product part-matching. No SIFT/SuperPoint/LoFTR in tree. | **DEFER** dense/learned. **WRAP** silhouette as Stage A cheap filter. **REIMPLEMENT_FROM_CONTRACT** Stages B–G (Bible §18). |
| 5.6 | Identity memory | `memory.WorldMemory`, `memory.identity.merge_identities` / `split_identity` / `alias_identity`; `test_world_memory.py` 19 tests | Core wheel; SQLite; no silent training. | **WRAP_WITH_ADAPTER** for store primitives. Searcher owns `ProductHypothesisGraph`. |
| 5.7 | Material / light | `materials.*`, `lighting.*`, `appearance.*` | Kernels; renderer parity (Cycles/WebGL), not leather-vs-suede on a listing photo. | **DEFER** / **REJECT** for MVP |
| 5.8 | World model / beliefs | `ocular.world.build_world_model` / `update_world_model`; `worldir`; `worlds` | Experimental / kernels / wrong schema (scene entities, not search campaigns). | **REIMPLEMENT_FROM_CONTRACT** Searcher search-world. **DEFER** ocular world. |
| 5.9 | Prediction / surprise | `ocular.predict.predict_next` / `list_surprises` | Experimental tracking, not listing contradictions. | **DEFER**. Searcher implements listing-level surprise itself. |
| 5.10 | Next-view | `v2.records.NextViewRequest`; `active_perception.planner.PlannerResult`; `world_brain.models.NextEvidenceRequest`; MCP `vision.ask_next_view` (ocular profile) | Schema is useful; planner is 3D-object views; ocular MCP is experimental. | **PORT_MINIMAL_COMPONENT** of the `NextViewRequest` **field set** into Searcher's own type (do not import V2). Do not take the 3D planner. |
| 5.11 | Browser evidence | `perception.browser` (CDP default, Playwright legacy); `perception.browser_lock.browser_slot`; ledger `web.capture` status available, receipt `PENDING_FINAL_RELEASE_RECEIPT` | Code + `test_browser_perception.py` 6 tests. Needs `[web]` + host Chrome. `worlds.browser` is kernels. | **WRAP_WITH_ADAPTER** for permitted listing capture. One browser slot. |
| 5.12 | Compare / evaluate / verify | Core MCP compare = digest; `comparison.images.compare_pair` = silhouette; `receipts.public` / `acceptance.receipts.verify_receipt`; no-fallback-pass is a VisionMCP policy (`capabilities_report` `no_fallback_physical_pass`) | Receipt verify has tests (`test_public_demos`). Product part compare does **not** exist. | **WRAP** receipts + silhouette. **REIMPLEMENT** product compare / authenticity. |
| 5.13 | Capability negotiation | `capabilities.capabilities_report`, `core_doctor_report`; `plugins.registry.PluginRegistry`; CLI `visionmcp capabilities` | Observed; core path loads zero plugins. | **WRAP_WITH_ADAPTER** — Searcher probes before every heavy call |
| 5.14 | Worker isolation | `mcp.blocking.run_blocking`; `browser_slot`; `core.optional.lazy_optional`; package split; binary worker (Ghidra) | Patterns are good. Ghidra worker is §5.15. | **WRAP** lazy-import + browser lock. **REIMPLEMENT** Searcher workers. **REJECT** Ghidra. |

### 2.3 Capabilities newer than Bible §5

| Capability | Where | Decision |
| --- | --- | --- |
| `ProfileName.SEARCH` / `GREED` + `vision.search.*` MCP | `profiles.py`, `greed/mcp.py` | **REJECT** as Searcher's crawler. Tools **register caller-supplied records**; they do not search the web. Profile is **not** in `PUBLIC_PROFILES`. |
| `AcquisitionOS` / `SearchExhaustionReceipt` | `acquisition/engine.py`, `acquisition/receipt.py` | **WRAP_WITH_ADAPTER** for the **exhaustion-receipt / honest BLOCKED source** pattern. Default registry is fixture/local/code/CAD — not clothing markets. Do not call `AcquisitionOS.search` as product search. |
| `SearchSource` protocol + `SourceStatus` | `acquisition/sources.py` | **WRAP** / re-type in Searcher source adapters |
| EvidenceGraph public resources | `evidence_graph/*` | **DEFER** as Searcher's primary store; optional later wrap |
| World Engine / World Brain | kernels | **DEFER** / **REJECT** as MTP stand-in (NA001 checkpoint race) |
| Visual Compiler / repair | kernels | **REJECT** (§5.15) |
| Native / spatial compilers | kernels | **REJECT** for clothing MVP |

### 2.4 Job Scraper

See `JOB_SCRAPER_CAPABILITY_HARVEST.md`. All **REIMPLEMENT_FROM_CONTRACT**
or **REJECT**. No wrap, no vendor, no package pin.

### 2.5 §5.15 + other rejections (complete)

| Item | Decision | Reason |
| --- | --- | --- |
| Apple parity corpora / evaluators | **REJECT** | §5.15; 297 cases, 0 complete passes |
| Frontend reconstruction compiler | **REJECT** | §5.15 |
| Source-code repair | **REJECT** | §5.15 |
| Blender / 3D generation | **REJECT** | §5.15 |
| COLMAP / full reconstruction | **REJECT** | §5.15 |
| Fur / organic | **REJECT** | §5.15 |
| Ghidra / binary | **REJECT** | §5.15 |
| Private benchmark vaults / hidden evaluators | **REJECT** | §5.15 |
| Generative weights / `vision.generate.authorized` | **REJECT** | §5.15; no weights bundled |
| Job stealth / impersonation / proxy / persistent profiles | **REJECT** | §6.10 |
| Job intern ranking / ATS fetchers / dashboard | **REJECT** | wrong domain |
| VisionMCP Studio as Searcher UI | **REJECT** | wrong product |
| Treating a block as empty source | **REJECT** | Bible §3.8 |

---

## 3. What Searcher must build (not reuse)

- Campaign controller + frontier + query compiler (§8–§15)
- Marketplace source adapters
- Listing normalization + dedupe
- Part-level match + authenticity engines (§18–§19)
- Real / Possibly Real policy (§20)
- Frontend (§24)

VisionMCP supplies perception/evidence **primitives**. Job Scraper
supplies a **contract**, not a library. MTP supplies nothing.
