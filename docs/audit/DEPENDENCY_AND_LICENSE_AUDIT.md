# Dependency and License Audit

Inspection date (UTC): 2026-08-16T04:48:46Z  
Donor SHA: `18ee3c06d27f04937d1681dea5fa2650131e4b2a`  
Sources read: pinned `LICENSE`, `NOTICE`,
`docs/legal/THIRD_PARTY_NOTICES.md`, `src/visionmcp/MODEL_LICENSES.json`,
`pyproject.toml`, Job Scraper `pyproject.toml`.

This audit **read committed license texts**. It did not install
packages or re-verify PyPI metadata.

---

## 1. VisionMCP project license

**Observed.** `LICENSE` at the pinned SHA is the Apache License 2.0,
January 2004. `NOTICE`:

```text
VisionMCP
Copyright 2026 VisionMCP contributors
Licensed under the Apache License, Version 2.0.
The import package and CLI are `visionmcp`. The public distribution
name is `visionmcp-ocular`; no legacy import shim is provided.
```

`pyproject.toml` classifier: `License :: OSI Approved :: Apache Software License`.

### What Apache-2.0 means for Searcher reuse

Searcher may depend on, wrap, and (if it later chooses) modify
VisionMCP under Apache-2.0 if it:

1. keeps a copy of the Apache-2.0 license for any distributed
   VisionMCP code or binary;
2. preserves copyright / NOTICE / attribution (including the
   **platformdirs** MIT notice — see below);
3. marks modified files if it ships a modified VisionMCP;
4. does not use "VisionMCP" / contributor names to endorse Searcher
   without permission.

Apache-2.0 is **not** copyleft. Searcher may remain under a different
license (including a proprietary one) for *its own* code. A public
Searcher release that **vendors** VisionMCP source must carry the
Apache-2.0 notice for those files. The settled architecture does
**not** vendor VisionMCP; it pins by SHA and wraps via an adapter.
That is the cleaner compliance path.

Patent grant: Apache-2.0 §3. Termination on patent litigation against
the Work applies to VisionMCP use.

---

## 2. Absorbed first-party code (attribution survives)

From `docs/legal/THIRD_PARTY_NOTICES.md` (donor-reported, dated
2026-07-29):

| Replaced package | First-party module | Relationship | Searcher duty |
| --- | --- | --- | --- |
| platformdirs | `visionmcp.core.paths` | MIT source **adapted** | If Searcher ships that module (via the package), the MIT text at `docs/legal/third_party_licenses/platformdirs-LICENSE.txt` must travel with it. |
| mcp | `visionmcp.mcp.host` | Reimplemented from the protocol | no attribution owed |
| pydantic | `visionmcp.validation.models` | Reimplemented | no attribution owed |

Core install third-party runtime dependencies: **none** (observed in
`pyproject.toml` `[project].dependencies = []`).

---

## 3. Recommended reuse path — what Searcher actually drags in

### 3.1 Primary path (core control plane, no extras)

`pip install` / pin `visionmcp-ocular==0.8.0a2` from git SHA
`18ee3c06` **with no extras**.

| Artifact | License | Blocks public Searcher? |
| --- | --- | --- |
| `visionmcp-ocular` core | Apache-2.0 + platformdirs MIT attribution | **No**, if notices are preserved |
| Companion wheel `visionmcp-ocular-kernels` | same project license (not installed on this path) | n/a |

Core doctor, `capabilities_report`, `ProjectStore`, `ArtifactStore`
(without imaging), MCP core handshake, and the public CLI `--help` /
`doctor --core` are designed not to import numpy, Pillow, cv2,
playwright, torch, or Blender (`package_architecture.CORE_FORBIDDEN_MODULES`).

**Caveat observed in source:** `visionmcp.receipts.public` **eagerly
imports** `visionmcp.compiler.service` (`receipts/public.py`).
`compiler` is a **kernels** subpackage. A core-only install may fail
on `import visionmcp.receipts.public`. Searcher's adapter must lazy
import receipt verification and treat a missing kernels extra as
`unavailable`, not crash the API health check.

`visionmcp-dev` **reported** (NA002) cannot print `--help` without
`imaging`. Do not use `visionmcp-dev` as Searcher's entry point.

### 3.2 Imaging extra (needed for real image observe / silhouette)

`visionmcp-ocular[imaging]` → numpy (BSD-family), Pillow (MIT-CMU /
HPND). **Not blocking** for a public Searcher.

`perception.media.analyze_image` also uses `cv2` via
`lazy_optional("cv2", extra="geometry or ocular")`. A Searcher that
calls `analyze_image` without opencv will get an honest extra error.
Plan: adapter catches `OptionalDependencyError` and degrades.

### 3.3 Web extra (listing capture)

`playwright` Apache-2.0 + host Chrome. Playwright itself is not
copyleft. Browser binaries are operator-installed.

### 3.4 Geometry / ocular extras — **do not take for MVP**

Donor notice (verified by them on an installed macOS wheel, dated
2026-07-29; **not re-verified here**):

- `opencv-python-headless` wrapper MIT, but the **macOS wheel ships
  GPL `libx264` / `libx265`**. Redistributing that wheel (or its
  dylibs) is a **publication risk**.
- `scipy` BSD-3-Clause + GCC runtime exception on bundled gfortran —
  generally not treated as a project-relicense trigger.
- `scikit-image` BSD-3-Clause; `trimesh` MIT.

**Flag for later public Searcher:** do not vendor or rebundle
`opencv-python-headless` wheels. Prefer `opencv-python-headless`
documented as an **operator-installed extra**, or a build that does
not ship x264/x265, if Searcher ever needs cv2 in a distributed
binary.

### 3.5 Models / torch

`models` extra does not declare torch. Plugin `torch` is
operator-supplied, never auto-downloaded (`MODEL_LICENSES.json`:
`bundled_model_weights.count = 0`). **Do not add torch to Searcher
MVP.**

---

## 4. Job Scraper licenses

`pyproject.toml` says `license = { text = "MIT" }`. **No LICENSE
file.** Dependencies (observed):

| Dep | Role | §6.10? |
| --- | --- | --- |
| httpx | HTTP | no |
| curl_cffi | TLS impersonation | **yes — reject** |
| pyrate-limiter | rate limit | no |
| tenacity | retry | no |
| pydantic | models | no |
| PyYAML | companies.yaml | no |
| structlog | logging | no |
| playwright | browser | ok if governed |
| tf-playwright-stealth | stealth | **yes — reject** |

Because Searcher is **not** depending on this package, these licenses
do not enter Searcher's tree. Do not vendor `scraper/`.

Personal data in the tree (CVs, `jobs.db`, Playwright profiles) must
never be copied into Searcher.

---

## 5. Publication blockers (summary)

| Item | Severity | Notes |
| --- | --- | --- |
| VisionMCP Apache-2.0 | ok | keep NOTICE + platformdirs MIT if the package is shipped |
| Core extras none | ok | primary path |
| numpy / Pillow | ok | imaging extra |
| playwright | ok | web extra; operator Chrome |
| opencv-python-headless macOS wheel GPL codecs | **flag** | do not rebundle; MVP should not require it |
| Job Scraper stealth deps | n/a | not adopted |
| Job Scraper missing LICENSE | n/a | not adopted |
| Absolute home paths in this audit | later scrub | acceptable in `docs/audit/` per task; strip before public docs |

Nothing in the **recommended** VisionMCP core+imaging path forces
Searcher itself to be Apache-2.0 or prevents a later public release,
provided notices travel with the dependency and opencv is not
rebundled.
