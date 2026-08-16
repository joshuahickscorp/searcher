# VisionMCP Capability Harvest

Inspection date (UTC): 2026-08-16T04:48:46Z  
Donor: VisionMCP  
Repository: `git@github.com:joshuahickscorp/visionmcp.git`  
Branch at pin: detached at tag `v0.8.0-alpha.2` (= `origin/main`)  
**SHA: `18ee3c06d27f04937d1681dea5fa2650131e4b2a`**  
Tree: `<home>/.searcher-donors/visionmcp` (read-only)  
Package: `visionmcp-ocular` `0.8.0a2`, import `visionmcp`,
`requires-python >=3.11`, Apache-2.0

Every `path:symbol` below was resolved with `rg` against this tree.
Distinguish: **observed** (in source), **reported** (donor docs/receipts),
**inferred** (this audit).

Tests were **not** run. Runtime receipts were **not** re-executed.

---

## 0. Integration surface (highest value)

### 0.1 Installable distribution — observed

| Field | Value |
| --- | --- |
| Dist name | `visionmcp-ocular` |
| Version | `0.8.0a2` (`src/visionmcp/__init__.py:__version__`) |
| Build | hatchling; wheel packages `src/visionmcp` with a long exclude list |
| Companion | `visionmcp-ocular-kernels==0.8.0a2` (`package_architecture.KERNELS_DISTRIBUTION`) |
| Core deps | **empty** (`pyproject.toml`) |
| Entry points | `visionmcp` → `visionmcp.cli.public:main`; `visionmcp-dev` → `visionmcp.cli.main:main` |
| PyPI | README **reports** production PyPI is not published in this alpha |

Core vs kernels split is **observed** in
`package_architecture.CORE_WHEEL_SUBPACKAGES` /
`KERNELS_WHEEL_SUBPACKAGES` and hatch `exclude`.

**Core wheel (Searcher may import):** `acceptance`, `acquisition`,
`artifacts`, `backends`, `boundary`, `cameras`, `cli`, `comparison`,
`core`, `datasets`, `evidence`, `evidence_graph`, `geometry`, `greed`,
`intelligence`, `mcp`, `memory`, `parity`, `perception`, `performance`,
`plugins`, `privacy`, `projects`, `receipts`, `security`, `simulation`,
`taste`, `v2`, `validation`, `vision`, `visual_geometry`, `worldir`.

**Kernels wheel (do not import at adapter load):**
`active_perception`, `app_build`, `appearance`, `benchmarks`, `binary`,
`blender`, `capture`, `cinematic`, `compiler`, `compilers`,
`constraints`, `critics`, `delivery`, `features`, `governance`,
`grooming`, `intent`, `lighting`, `materials`, `models`, `ocular`,
`optimization`, `orchestration`, `organic`, `parametric`, `procedural`,
`reconstruction`, `render`, `repair`, `repairs`, `review`,
`scheduling`, `scoring`, `sdk`, `spatial`, `studio`, `visual`,
`workflows`, `world_brain`, `world_engine`, `worlds`.

### 0.2 Python import surface — observed

Stable for Searcher (core, lazy-safe):

- `visionmcp.capabilities:capabilities_report`, `core_doctor_report`
- `visionmcp.api:public_api_versions`
- `visionmcp.profiles:ProfileName`, `CORE_TOOLS`, `tool_allowed`
- `visionmcp.projects.store:ProjectStore`
- `visionmcp.artifacts.store:ArtifactStore`
- `visionmcp.core.imaging:require_imaging`, `imaging_available`
- `visionmcp.core.optional:lazy_optional`, `OptionalDependencyError`
- `visionmcp.plugins.registry:PluginRegistry`
- `visionmcp.memory.world_memory:WorldMemory`
- `visionmcp.acquisition.engine:AcquisitionOS` (pattern, not crawler)
- `visionmcp.acquisition.receipt:SearchExhaustionReceipt`
- `visionmcp.v2.records:NextViewRequest`

Needs `imaging` extra (lazy):

- `visionmcp.perception.media:ImageFileAdapter`, `analyze_image`
- `visionmcp.evidence.references:inspect_image`, `ReferenceIngestor`
- `visionmcp.comparison.images:compare_pair`, `silhouette_mask`

Needs `web` extra + Chrome (lazy):

- `visionmcp.perception.browser` (module; CDP default)
- `visionmcp.perception.browser_lock:browser_slot`

**Trap:** `visionmcp.receipts.public` **eagerly** imports
`visionmcp.compiler.service` (kernels). Do not import this module at
adapter load.

### 0.3 CLI — observed (`cli/public.py:build_parser`)

`visionmcp --version|doctor|serve|studio|capabilities|benchmark|demo|verify|receipt|cache|model|project|artifact|plugin`

Searcher-relevant: `doctor --core`, `capabilities --json`,
`receipt verify`, `artifact verify`, `project create|status`.

`serve --profile` default `core`, transport **stdio only**.

`visionmcp-dev` is the legacy full CLI; NA002 reports it imports
Pillow at `--help`. **Do not use.**

### 0.4 MCP — observed

Factory: `mcp.factory:create_server` → core
`mcp.core_server:create_core_server` (15 tools, zero plugins).

Core tools (`profiles.CORE_TOOLS`):
`vision.capabilities`, `vision.observe`, `vision.query`,
`vision.explain_region`, `vision.compare`, `vision.verify`,
`vision.progress`, `vision.review_queue`, `vision.open_project`,
`vision.close_project`, `vision.list_artifacts`, `vision.get_artifact`,
`system.doctor`, `project.create`, `project.status`.

`vision.observe` accepts only `image.file` / `video.file` /
`camera.frame` on core. `vision.compare` is
`core.digest_compare` (identical manifest digest).

Search tools live in `greed/mcp.py:register_search_tools` and are
attached only for profiles `SEARCH`, `GREED`, `DEV`. `SEARCH` is
**not** in `PUBLIC_PROFILES`.

### 0.5 Recommended path

See `REUSE_DECISIONS.md` §1. Primary = in-process adapter. Fallback =
CLI subprocess. Missing capability → structured degrade, never
fabricate.

---

## 1. Donor-reported capability ledger

File: `artifacts/capability-ledger.json`  
Schema: `visionmcp.capability-ledger/v1`  
**Reported** product version inside the ledger: `0.8.0a1` — **stale
relative to** `0.8.0a2` in `pyproject.toml` / `__init__.py`.

| id | status | ceiling | receipt (reported) | Searcher |
| --- | --- | --- | --- | --- |
| core.project-artifacts | available | OBSERVED | `artifacts/release/public-alpha-source-authority.json` | WRAP |
| core.mcp-resources | available | OBSERVED | `PENDING_FINAL_RELEASE_RECEIPT` | DEFER |
| web.capture | available | OBSERVED | `PENDING_FINAL_RELEASE_RECEIPT` | WRAP (if needed) |
| compiler.visual-program | available | CANDIDATE | `compiler-transfer.json` | REJECT |
| compiler.repair-plan | available | INFERRED | PENDING | REJECT |
| studio.local-workspace | available | OBSERVED | PENDING | REJECT |
| core.receipts | available | VERIFIED_DIGEST | PENDING | WRAP |
| binary.ghidra | available | DECOMPILER_APPROXIMATION | PENDING | REJECT |
| 3d.blender | available | GENERATED_SOURCE_KNOWN | PENDING | REJECT |
| benchmark.escrow | available | ESCROW_VERIFIED | public-alpha-source-authority | REJECT |
| core.plugin-sdk | available | DECLARED | PENDING | WRAP (probe only) |
| ocular.perception | experimental | DERIVED | `artifacts/ocular/honest-baseline/BASELINE.json` — **FILE ABSENT at this SHA** | DEFER |
| compiler.apple-parity04 | **failed** | MEASURED | 297 cases, 0 complete passes | REJECT |
| world-engine.public-sdk | experimental | DECLARED | `artifacts/world-engine/step-35/` | DEFER |

`public-alpha-source-authority.json` **reports** `product_base_sha`
`2562502edc754e339a6ee1bc8889dc98be5d2345` and
`passed: true` with one candidate test run
`failed=1 passed=1324`. That SHA is **not** `18ee3c06`. Treat as
historical.

---

## 2. Per-component records (Searcher-relevant)

Common fields for this section unless overridden:

- donor: VisionMCP
- repository: `joshuahickscorp/visionmcp`
- branch: detached `v0.8.0-alpha.2` / `origin/main`
- SHA: `18ee3c06d27f04937d1681dea5fa2650131e4b2a`
- license: Apache-2.0 (+ platformdirs MIT in `core.paths`)

### 2.1 `visionmcp.capabilities:capabilities_report`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/capabilities.py:capabilities_report` |
| purpose | Capability negotiation without downloading weights or starting workers |
| input | `profile`, optional schema byte count / tool names |
| output | `{available, blocked, experimental, plugins, blockers, api_versions, network, authority}` |
| dependencies | `profiles`, `plugins.builtins` (probe only) |
| tests | `tests/test_profiles_and_plugins.py` (14 `def test_`, counted) |
| runtime | **reported** via CLI/MCP; not re-run |
| ceiling | DECLARED / probed health |
| limitations | Ocular numbers are hardcoded constants, not live measurements |
| security | none significant |
| performance | intended milliseconds; no process spawn |
| **adoption** | **WRAP_WITH_ADAPTER** |

Sister: `core_doctor_report` — offline, forbids optional imports.

### 2.2 `visionmcp.projects.store:ProjectStore`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/projects/store.py:ProjectStore` |
| purpose | Portable SQLite project; `STATUS_COUNT_TABLES` is a public counts shape |
| input | root path, name, `FidelityLevel` |
| output | `create` / `open` / `status` / `connection` |
| dependencies | stdlib sqlite3 |
| tests | `test_profiles_and_plugins.py`; CLI project tests |
| **adoption** | **WRAP_WITH_ADAPTER** — Searcher may host a VisionMCP project per campaign for artifacts, or wrap the store behind Searcher paths |

### 2.3 `visionmcp.artifacts.store:ArtifactStore`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/artifacts/store.py:ArtifactStore` |
| purpose | SHA-256 content-addressed bytes; symlink refuse; tamper detect on verify |
| input | file path + media type |
| output | `ArtifactRecord` (digest, size, media_type, relative path) |
| dependencies | `projects.ProjectStore`, `core.util.sha256_file` |
| security | `SecurityError` on symlink / dest escape / digest mismatch |
| **adoption** | **WRAP_WITH_ADAPTER** |

### 2.4 `visionmcp.receipts.public:verify_any_receipt`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/receipts/public.py:verify_any_receipt` |
| purpose | Schema-aware receipt verify + tamper reject |
| input | receipt path; optional project |
| output | `{valid, ok, failures, schema, receipt_sha256}` |
| dependencies | **eager** `visionmcp.compiler.service` (kernels!) then `acceptance.receipts` |
| tests | `test_public_demos.py` (4 functions, counted) |
| ceiling | VERIFIED_DIGEST (integrity ≠ fidelity) — ledger |
| **adoption** | **WRAP_WITH_ADAPTER** with lazy import; degrade if kernels missing |

### 2.5 `visionmcp.evidence.references:inspect_image`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/evidence/references.py:inspect_image` |
| purpose | Decode, EXIF orientation, ICC digest, camera/lens tags, blur/exposure warnings |
| input | `Path` |
| output | `(metadata, quality)` dicts |
| dependencies | Pillow (`Image`, `ImageOps`, `ExifTags`) |
| **adoption** | **WRAP_WITH_ADAPTER** (imaging extra) |

`ReferenceIngestor` persists reference items into the project.

### 2.6 `visionmcp.perception.media:ImageFileAdapter` / `analyze_image`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/perception/media.py:ImageFileAdapter`, `analyze_image` |
| purpose | Observe a local image into content-addressed source + normalized PNG + region graph + optional Tesseract OCR + perceptual hash |
| input | `{path}`, config `{maximum_dimension, ocr, maximum_regions}` |
| output | `CaptureOutcome` via `CaptureBus` |
| dependencies | Pillow, numpy; **cv2** via `lazy_optional`; tesseract optional |
| limitations | Regions are Canny contours, not product parts. OCR requires host tesseract. `environment()` reads `cv2.__version__` (will fail without opencv). |
| **adoption** | **WRAP_WITH_ADAPTER** — call only after `imaging_available()`; catch missing cv2 |

`CaptureBus` / `AdapterRegistry` / `SensorAdapter`:
`perception/bus.py`. Core registers `ImageFileAdapter` +
`VideoFileAdapter` only.

### 2.7 `visionmcp.comparison.images:compare_pair` / `silhouette_mask`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/comparison/images.py:compare_pair`, `silhouette_mask` |
| purpose | Alpha-or-corner-background silhouette IoU for reference vs **render** |
| input | two image paths + residual out path |
| output | metrics incl. `silhouette_iou`; residual PNG |
| dependencies | Pillow; `performance.kernels.silhouette.compare_mask_pair` |
| limitations | Built for compiler/render residuals, not listing-vs-reference part match. Core MCP `vision.compare` does **not** call this. |
| **adoption** | **WRAP_WITH_ADAPTER** as Stage A cheap filter only |

### 2.8 `visionmcp.perception.browser` + `browser_lock:browser_slot`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/perception/browser.py` (module), `browser_lock.py:browser_slot` |
| purpose | Governed browser capture (pixels, DOM, a11y, style, network); single cross-process engine slot |
| input | URL + capture config; `browser_slot(timeout=, blocking=)` |
| output | capture artifacts; `BrowserBusy` if slot held |
| dependencies | `[web]` playwright and/or CDP + host Chrome; `worlds.browser` for CDP path is **kernels** |
| tests | `test_browser_perception.py` 6; `test_browser_world.py` exists |
| ledger | `web.capture` available, receipt PENDING |
| security | scheme allowlist http/https; secret-key redaction regex |
| performance | one engine; 1800s default slot timeout |
| **adoption** | **WRAP_WITH_ADAPTER** for permitted listing pages. Default 1 browser. |

### 2.9 `visionmcp.memory.world_memory:WorldMemory` + identity

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/memory/world_memory.py:WorldMemory`; `memory/identity.py:merge_identities` |
| purpose | Append-only entity versions, merge/split/alias, drift gate, no silent training |
| input | sqlite path; `EntityVersion` / identity events |
| output | versions, `RetrievalHit`s, `DeletionReceipt` |
| tests | `test_world_memory.py` 19 |
| **adoption** | **WRAP_WITH_ADAPTER** for primitives. Searcher owns the hypothesis graph. |

### 2.10 `visionmcp.evidence_graph.graph:EvidenceGraph`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/evidence_graph/graph.py:EvidenceGraph` |
| purpose | Typed causal graph, fail-closed authority, supersession |
| tests | `test_evidence_graph.py` 16 + several siblings |
| **adoption** | **DEFER** as Searcher's primary store. Optional later wrap. Searcher campaign state is owned by Searcher. |

### 2.11 `visionmcp.v2.records:NextViewRequest`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/v2/records.py:NextViewRequest` |
| purpose | `missing_uncertainty`, `expected_reduction`, capture/human instructions, priority 0–10 |
| **adoption** | **PORT_MINIMAL_COMPONENT** of the **field set** into a Searcher type. Do not import V2 into Searcher's public API. |

`world_brain.models.NextEvidenceRequest` is kernels — do not import.

### 2.12 `visionmcp.active_perception.planner`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/active_perception/planner.py:consumer_object_candidates` |
| purpose | Next-best-view for 3D consumer objects (underside, 1600px, 0.35m) |
| wheel | **kernels** / ocular extra |
| **adoption** | **DEFER** / **REJECT** for clothing MVP (wrong view grammar). Keep the *idea*. |

### 2.13 `visionmcp.ocular.*` (experimental)

| Symbol | Purpose | Adoption |
| --- | --- | --- |
| `ocular.proposals:propose_dense_features` | Canny + Lab/HOG/moments; "no learned backbone" | **DEFER** |
| `ocular.segment` | Classical GrabCut/watershed; `SEGMENT_AUTHORITY_CEILING = SENSOR_DERIVED` | **DEFER** |
| `ocular.world:build_world_model` / `update_world_model` | Scene entities + beliefs | **DEFER** |
| `ocular.predict:predict_next` / `list_surprises` | Tracking surprise | **DEFER** |
| `ocular.track` / `stream` | Recorded streams | **DEFER** |
| `ocular.calibration` / `gaze` / `retina` | Sensor/gaze | **DEFER** |

Ledger **reports** proposal recall 0.648 / precision 0.12–0.39 and
cites `artifacts/ocular/honest-baseline/BASELINE.json`. **Observed:
that directory does not exist at this SHA.** Authority ceiling for
ocular claims at this pin is **unverified / experimental**.

### 2.14 `visionmcp.acquisition.engine:AcquisitionOS`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/acquisition/engine.py:AcquisitionOS.search` |
| purpose | Search-first asset portfolio + `SearchExhaustionReceipt`; generation forbidden until exhaustion |
| input | `SearchQuery` (text/image/silhouette/geometry/metadata/code) |
| output | `AcquisitionPortfolio` |
| default sources | `local-project`, `history`, `official-product`, `public-repository`, `licensed-library`, `archive`, `package-registry`, `cad-ar-reference` — **not Grailed/Yahoo/YahooJP** |
| network adapters | **not required**; fixtures + `MissingSearchSource` → structured BLOCKED |
| tests | `test_acquisition_os.py` 19 |
| **adoption** | **WRAP_WITH_ADAPTER** for exhaustion/BLOCKED/rights-unknown-is-reject. **REJECT** as clothing search. |

`acquisition/sources.py:SearchSource`, `SourceStatus`,
`FixtureSearchSource`, `MissingSearchSource` — same decision.

`acquisition/models.py:SearchQuery`, `SearchHit`,
`CandidateDisposition`, `RejectionReason` — wrap or re-type.

### 2.15 `visionmcp.greed.mcp:register_search_tools`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/greed/mcp.py:register_search_tools` |
| purpose | MCP tools `vision.search.plan|web|official|…` |
| observed behaviour | `vision.search.web` **registers** `records` supplied by the caller (`register_results`). It does not fetch the internet. |
| **adoption** | **REJECT** as Searcher's discovery engine |

### 2.16 `visionmcp.plugins.registry:PluginRegistry`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/plugins/registry.py:PluginRegistry` |
| purpose | Empty at start; declare not auto-load |
| builtins | blender, playwright, colmap, torch, ocular-classical (`plugins/builtins.py`) |
| **adoption** | **WRAP_WITH_ADAPTER** (probe). Do not load torch/colmap/blender. |

### 2.17 `visionmcp.mcp.core_server:create_core_server`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/mcp/core_server.py:create_core_server` |
| purpose | 15-tool core MCP; no browser/Blender/torch import |
| **adoption** | **DEFER** (fallback isolation). Not the primary path. |

### 2.18 `visionmcp.core.optional:lazy_optional` / `core.imaging`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/core/optional.py:lazy_optional`; `core/imaging.py:require_imaging` |
| purpose | Honest extra errors; no silent weight download |
| **adoption** | **WRAP_WITH_ADAPTER** — Searcher adapter must use the same discipline |

### 2.19 `visionmcp.security.paths`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/security/paths.py` (`confined_path`, `assert_no_arbitrary_read`, `safe_mode`) |
| purpose | Project-root confinement, symlink reject |
| **adoption** | **WRAP_WITH_ADAPTER** when touching VisionMCP projects |

### 2.20 `visionmcp.features.detector:detect_label_mask`

| Field | Record |
| --- | --- |
| path / symbol | `src/visionmcp/features/detector.py:detect_label_mask` |
| purpose | Recover **synthetic** RGB feature-ID labels |
| wheel | kernels |
| **adoption** | **REJECT** as a real segmenter |

### 2.21 `visionmcp.materials.parity` / lighting / appearance

Renderer-parity harness (Cycles / WebGL / poster). Kernels.
**DEFER** / **REJECT** for listing-photo material separation.

### 2.22 World Engine / World Brain / Studio / Compiler / Binary / Blender / Reconstruction

All kernels or §5.15. **REJECT** or **DEFER** as noted in
`REUSE_DECISIONS.md`. Not harvested as Searcher MVP capabilities.

---

## 3. Recursive subsystem inventory

All top-level packages under `src/visionmcp/` at this SHA. Adoption is
for **Searcher MVP clothing search**, not VisionMCP's own roadmap.

| Subsystem | Wheel | Observed purpose | Adoption |
| --- | --- | --- | --- |
| `acceptance` | core | Receipt/acceptance helpers | WRAP (via receipts) |
| `acquisition` | core | AcquisitionOS, sources, exhaustion | WRAP pattern; REJECT as crawler |
| `active_perception` | kernels | Next-best 3D view | DEFER |
| `app_build` | kernels | App construction from visual ref | REJECT |
| `appearance` | kernels | Fixed-camera material acceptance | DEFER |
| `artifacts` | core | Content-addressed store | WRAP |
| `backends` | core | Engine ABI / registry | DEFER |
| `benchmarks` | kernels | Parity / escrow / one-prompt | REJECT |
| `binary` | kernels | Ghidra worker | REJECT |
| `blender` | kernels | Headless Blender | REJECT |
| `boundary` | core | Public IR/schema boundary | DEFER |
| `cameras` | core | Camera recovery backends | DEFER |
| `capture` | kernels | Video frame extraction | DEFER |
| `cinematic` | kernels | Scroll-bound camera paths | REJECT |
| `cli` | core | Public + dev CLI | WRAP public CLI as fallback |
| `comparison` | core | Silhouette / render compare | WRAP cheap filter |
| `compiler` | kernels | VisualProgramIR | REJECT |
| `compilers` | kernels | Native/spatial compilers | REJECT |
| `constraints` | kernels | Geometric constraints | DEFER |
| `core` | core | Paths, optional, imaging, models | WRAP |
| `critics` | kernels | 13 perceptual critics | DEFER |
| `datasets` | core | Synthetic training contracts | REJECT |
| `delivery` | kernels | Web LOD/compression | REJECT |
| `evidence` | core | References, masks, duplicates, pursuit | WRAP inspect; DEFER rest |
| `evidence_graph` | core | Causal evidence graph | DEFER |
| `features` | kernels | Synthetic feature IDs | REJECT as segmenter |
| `geometry` | core | Scene/geometry ops | DEFER |
| `governance` | kernels | Experiment governance | DEFER |
| `greed` | core | Search cortex MCP + rights | REJECT as crawler; WRAP rights idea |
| `grooming` | kernels | Fur | REJECT |
| `intelligence` | core | Reconstruction intelligence | DEFER |
| `intent` | kernels | One-prompt IntentIR | REJECT |
| `lighting` | kernels | Inverse lighting | DEFER |
| `materials` | kernels | Material parity | DEFER |
| `mcp` | core | Host, core server, factory | DEFER as bus; WRAP capabilities tool idea |
| `memory` | core | WorldMemory | WRAP |
| `models` | kernels | Weight enrollment (none bundled) | REJECT |
| `ocular` | kernels | Experimental perception | DEFER |
| `optimization` | kernels | Multi-objective fit | DEFER |
| `orchestration` | kernels | "Beast Mode" | REJECT |
| `organic` | kernels | Organic gen | REJECT |
| `parametric` | kernels | Technical components | DEFER |
| `parity` | core | Apple/web/spatial parity | REJECT |
| `perception` | core | Media + browser + bus | WRAP |
| `performance` | core | Kernels / budgets | DEFER |
| `plugins` | core | Registry + builtins | WRAP probe |
| `privacy` | core | Local visual lifecycle | WRAP policy |
| `procedural` | kernels | Procedural worlds | REJECT |
| `projects` | core | ProjectStore | WRAP |
| `receipts` | core | Public verify | WRAP (lazy) |
| `reconstruction` | kernels | Multi-method 3D | REJECT |
| `render` | kernels | Draft-verify render | REJECT |
| `repair` / `repairs` | kernels | RepairOS | REJECT |
| `review` | kernels | Human review service | DEFER |
| `scheduling` | kernels | SQLite jobs | DEFER |
| `schemas` | (json) | JSON schemas | DEFER |
| `scoring` | kernels | 0–110 capability scores | REJECT |
| `sdk` | kernels | World Engine public SDK | DEFER |
| `security` | core | Path confinement | WRAP |
| `simulation` | core | Repair simulation | DEFER |
| `spatial` | kernels | Depth / point clouds | DEFER |
| `studio` | kernels | Local IDE | REJECT |
| `taste` | core | TasteIR | DEFER |
| `v2` | core | V2 records incl. NextViewRequest | PORT field set |
| `validation` | core | StrictModel | DEFER |
| `vision` | core | Geometry-backend contracts | DEFER |
| `visual` | kernels | Visual-oracle registry | DEFER |
| `visual_geometry` | core | Manufactured-form audit | DEFER |
| `workflows` | kernels | Reconstruction workflows | REJECT |
| `world_brain` | kernels | Assurance planner | DEFER |
| `world_engine` | kernels | Step census / grading | DEFER |
| `worldir` | core | WorldIR types | DEFER |
| `worlds` | kernels | Browser/native/spatial worlds | DEFER (browser world is kernels; `perception.browser` is core) |
| `api.py` | core | Wire versions | WRAP |
| `capabilities.py` | core | Negotiation | WRAP |
| `profiles.py` | core | Tool allowlists | WRAP |
| `package_architecture.py` | core | Wheel map / budgets | WRAP (read-only) |

~747 Python files under `src/visionmcp/` (counted).

---

## 4. Map onto Bible §5 (evidence quality)

| § | Exists at SHA? | Evidence | Decision |
| --- | --- | --- | --- |
| 5.1 Evidence spine | yes — artifacts, projects, receipts, evidence_graph | code + tests counted; receipts often bind older SHAs | WRAP |
| 5.2 Calibration | yes — inspect_image, ImageFileAdapter | code observed; imaging extra | WRAP |
| 5.3 Attention / crops | partial — ocular + Canny regions | ocular experimental; baseline file missing | DEFER ocular; Searcher crops |
| 5.4 Segmentation | classical only | ocular.segment; silhouette | DEFER / wrap silhouette |
| 5.5 Dense / correspondence | classical HOG/Lab only; digest compare | no learned matcher | DEFER + REIMPLEMENT match |
| 5.6 Identity memory | yes — WorldMemory | 19 tests counted | WRAP store; own graph |
| 5.7 Material / light | 3D parity, not listing photos | kernels | DEFER |
| 5.8 World / beliefs | ocular world + worldir | experimental / wrong schema | REIMPLEMENT search world |
| 5.9 Prediction / surprise | ocular.predict | experimental | DEFER |
| 5.10 Next-view | NextViewRequest + 3D planner | schema good; planner wrong | PORT fields |
| 5.11 Browser | perception.browser + lock | 6 tests counted; PENDING receipt | WRAP |
| 5.12 Compare / verify | digest + silhouette + receipts | product compare absent | WRAP receipts; REIMPLEMENT match |
| 5.13 Negotiation | capabilities_report | 14 tests counted | WRAP |
| 5.14 Isolation | lazy extras, browser_slot, wheel split | code observed | WRAP patterns |
| 5.15 Exclusions | all present as packages | — | REJECT |

---

## 5. Known donor defects that affect Searcher

From `NEXT_ALPHA_BACKLOG.md` / `.json` (**reported**, not reproduced):

- NA001: terminal checkpoint double-append under concurrency (world_brain)
- NA002: `visionmcp-dev --help` needs imaging
- NA009: intermittent census test under `-n 24`

From ALPHA lock (**reported**): Gate A unresolved; 22/45 world-engine
gates STALE; macOS-only alpha; installed footprint gate failed.

From this inspection: ocular baseline path missing; capability ledger
still says `0.8.0a1`; `receipts.public` imports kernels.

---

## 6. How to re-check a citation

```bash
rg -n "def capabilities_report" ~/.searcher-donors/visionmcp/src/visionmcp/capabilities.py
git -C ~/.searcher-donors/visionmcp rev-parse HEAD
# expect 18ee3c06d27f04937d1681dea5fa2650131e4b2a
```
