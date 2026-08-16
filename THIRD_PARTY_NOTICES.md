# Third-party notices

Searcher itself is Apache-2.0. Copyright 2026 Joshua Hicks. See
[LICENSE](LICENSE).

Licenses below were read from installed package metadata on 2026-08-16
via `importlib.metadata`, except where a row says otherwise. This is
not legal advice.

A longer donor-license discussion, including why Searcher must not
rebundle an `opencv-python-headless` wheel that ships GPL codecs, is
in [docs/audit/DEPENDENCY_AND_LICENSE_AUDIT.md](docs/audit/DEPENDENCY_AND_LICENSE_AUDIT.md).

## Runtime dependencies (`pyproject.toml`)

| Package | Role | License (metadata) |
|---|---|---|
| pydantic | schema / records | MIT |
| pillow | image decode and classical features | MIT-CMU (HPND-derived PIL license) |
| httpx | honest HTTP client | BSD-3-Clause |
| selectolax | HTML parse | MIT |
| fastapi | HTTP API | MIT |
| uvicorn[standard] | ASGI server | BSD-3-Clause |
| python-multipart | multipart uploads | Apache-2.0 |

`uvicorn[standard]` also pulled in, on this install: `httptools` (MIT),
`uvloop` (MIT), `watchfiles` (MIT), `websockets` (BSD-3-Clause),
`pyyaml` (MIT), plus the usual FastAPI/httpx stack (`starlette`
BSD-3-Clause, `anyio` MIT, `httpcore` BSD-3-Clause, `certifi`
MPL-2.0, `idna` BSD-3-Clause, `h11` MIT, `click` BSD-3-Clause,
`pydantic-core` MIT, `annotated-types` MIT, `typing-extensions`
PSF-2.0). The lockfile (`uv.lock`) is the complete pin.

## Optional extra

| Extra | Package | License | Notes |
|---|---|---|---|
| `browser` | playwright | Apache-2.0 (upstream; not installed by default `uv sync`) | Operator-installed Chromium. No stealth wrapper. |

OpenCV is **not** a declared Searcher dependency. Matching uses it
only if the operator already has `cv2` on the path.

## Dev dependencies

| Package | Role | License (metadata) |
|---|---|---|
| pytest | tests | MIT |
| pytest-timeout | test timeouts | MIT |
| hypothesis | property tests | MPL-2.0 |
| ruff | lint / format | MIT |
| mypy | typecheck | MIT |
| httpx2 | Starlette TestClient compatibility | BSD-3-Clause |

Build backend: `hatchling` (MIT, upstream). It is not a runtime
dependency.

## VisionMCP donor

| Field | Value |
|---|---|
| Project | `visionmcp-ocular` 0.8.0a2 |
| SHA | `18ee3c06d27f04937d1681dea5fa2650131e4b2a` |
| License | Apache-2.0 (observed `LICENSE` at that SHA) |
| NOTICE | Copyright 2026 VisionMCP contributors |
| Install | `scripts/setup_donor.sh` → `$SEARCHER_DONOR_DIR` |
| Remote | `https://github.com/joshuahickscorp/visionmcp` |

Searcher wraps it. It does not vendor the source. A public release
that later vendors VisionMCP must carry Apache-2.0 and the
platformdirs MIT attribution described in the donor `NOTICE`. Core
VisionMCP at this SHA declares no third-party runtime dependencies.

## Job Scraper frozen snapshot

| Field | Value |
|---|---|
| Snapshot | `$SEARCHER_JOBSCRAPER_FROZEN_DIR` |
| Manifest digest | `3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2` |
| Freeze date | 2026-08-16 |
| License | MIT, declared in the donor `pyproject.toml`. The snapshot has no `LICENSE` file. |
| Git SHA | none — the donor was not a git repository |

Only honest primitives were ported (per-host pacing, robots cache,
retry ceiling, circuit breaker, idempotent work key, fetch log,
live-status classification). The Bible §6.10 evasion surface was
**rejected** and is listed in
`src/searcher/integrations/job_scraper/provenance.py` `EXCLUSIONS`:
stealth Playwright wrappers, TLS impersonation (`curl_cffi`), proxy
pools, UA rotation, persistent browser profiles, automation-controlled
flags, applicant scoring. Evidence:
`tests/unit/test_donor_rejection.py`.

The snapshot itself is not vendored into this repository.

## MTP

Absent. Nothing adopted. See
[docs/audit/MTP_CAPABILITY_HARVEST.md](docs/audit/MTP_CAPABILITY_HARVEST.md).
