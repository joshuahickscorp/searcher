# Searcher

Evidence-ranked multimodal search for hard-to-find physical products.

Give it photographs, optional text, and optional tags. It treats that
input as a hypothesis, not as authority. It analyzes the images, forms
competing identity hypotheses, compiles query families, and — when a
live discovery layer is wired into the running process — searches
admitted public sources, compares candidates at part level, scores
authenticity separately from item match, and returns two lists.

Searcher is **not** a professional authenticator. A placement in Real
is an evidence ranking under the current policy version, not a
certificate of genuineness. Read [LIMITATIONS.md](LIMITATIONS.md) and
[CLAIMS.md](CLAIMS.md) before repeating anything about what it can do.

Standing authority:
[docs/SEARCHER_FULL_IMPLEMENTATION_BIBLE.md](docs/SEARCHER_FULL_IMPLEMENTATION_BIBLE.md).

Status: pre-alpha. Version `0.1.0`. There is **no hosted API**. The
public GitHub Pages UI talks to an API you run on localhost.

## The two tabs

| Tab | What it means | What it is not |
|---|---|---|
| **Real** | High confidence under the available images, the active bucket policy (`matching-1` by default), a calibrated authenticity interval, and a live verified listing. | Not a professional authentication. Not a purchase recommendation. |
| **Possibly Real** | A plausible item match with incomplete, conflicting, or uncalibrated evidence. Uncertain candidates are preserved here. | Not a counterfeit shop. Hard mismatches and strong replica/scam vetoes are hidden, not shown as “possibly real.” |

There is no public Fake tab. Hidden candidates are not published as
accusations. See [SEARCHER_BUCKET_POLICY.md](SEARCHER_BUCKET_POLICY.md)
and [SEARCHER_AUTHENTICITY_POLICY.md](SEARCHER_AUTHENTICITY_POLICY.md).

## What this tree actually does today

Implemented and covered by tests:

- Upload validation, EXIF quarantine, reference analysis, hypothesis
  portfolio, and query compilation.
- A campaign state machine with checkpoints, cancellation, crash
  resume, and hash-chained receipts.
- Source adapters for the admitted set in
  [SOURCE_POLICY.md](SOURCE_POLICY.md). International and
  `review_required` adapters ship **disabled**.
- A matching and authenticity stack that uses **classical** local
  descriptors (Pillow BRIEF-like, OpenCV ORB when present). VisionMCP
  at the pinned SHA has no learned feature backbone, no part matcher,
  and no logo detector.
- An HTTP API (FastAPI, SQLite WAL, SSE) and a dependency-free static
  UI in `web/`.

Honest gap in the running API process:

`scripts/run_api.sh` finishes the reference-analysis and query wave
and then stops with terminal status `BLOCKED`. Live listing discovery,
retrieval, matching, authenticity, and ranking are **not invoked** by
that process today. The packages exist in `src/searcher/` and have
their own tests; the API reports `discovery.available = false` and
`routing.available = false`. An empty result list after `BLOCKED` is
not a finding that the item does not exist.

No public benchmark has been run. Thresholds are provisional. No
precision, recall, or latency number in this repository is a measured
product claim.

## Quickstart

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
scripts/setup_donor.sh    # optional; pins VisionMCP at 18ee3c06…
scripts/run_api.sh        # binds 127.0.0.1:8765 and serves web/
```

Open http://127.0.0.1:8765/

Without the donor, Searcher still decodes images with Pillow. Visual
donor lanes stay blocked and nothing is promoted to Real through a
degraded path. `searcher capabilities` reports `importable: False`.

The donor is not a PyPI package. `scripts/setup_donor.sh` clones the
audited SHA into `$SEARCHER_DONOR_DIR` (default
`$HOME/.searcher-donors/visionmcp`) and installs it. See
[docs/architecture/DONOR_SETUP.md](docs/architecture/DONOR_SETUP.md).

## GitHub Pages UI → local API

The static files in `web/` are what GitHub Pages would serve. They
contain no secrets. `web/config.js` sets `API_BASE` to `""` (same
origin). On Pages there is no same-origin API, so point the page at
your machine:

1. Start the API: `scripts/run_api.sh`
2. Open the Pages URL with `?api=http://127.0.0.1:8765`
3. Set `SEARCHER_CORS_ORIGINS` to the Pages origin. The default CORS
   list is localhost only; a `github.io` origin is otherwise refused.

The browser must be able to reach `127.0.0.1` on your computer. There
is no hosted Searcher API to point at instead.

`web/dev/` is a stub for UI development. It is not part of the Pages
site.

## More

- [LIMITATIONS.md](LIMITATIONS.md) — what Searcher does not claim
- [CLAIMS.md](CLAIMS.md) — the only sentences currently entitled
- [PRIVACY.md](PRIVACY.md) — uploads, deletion, no training, no telemetry
- [SECURITY.md](SECURITY.md) — threat model and what is implemented
- [ARCHITECTURE.md](ARCHITECTURE.md) — system graph and module map
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — licenses and donors
- [LICENSE](LICENSE) — Apache-2.0, Copyright 2026 Joshua Hicks
