# Architecture

A map of what this repository implements. The standing design is
Bible §8. The packages live under `src/searcher/` as one
distribution; see [docs/architecture/MODULE_MAP.md](docs/architecture/MODULE_MAP.md).

## High-level graph (Bible §8.1)

```text
WEB APP  (web/)
  images | text | tags | progress | Real | Possibly Real
        |  HTTPS or localhost HTTP + SSE
API GATEWAY  (src/searcher/api/)
  validation | upload | search creation | result retrieval
        |
SEARCH CAMPAIGN CONTROLLER  (src/searcher/campaigns/)
  state machine | budget | checkpoints | receipts | stop law
        |
   +----+------------+--------------+---------------+
   |                 |              |               |
REFERENCE        HYPOTHESIS &    SOURCE          RESULT
ANALYZER         QUERY ENGINE    BROKER          PUBLISHER
VisionMCP        Searcher        Job Scraper     Searcher
adapter          (hypotheses,    primitives      (ranking,
                 queries)        + adapters      views)
        |
CANDIDATE + EVIDENCE STORE
  content addressed | normalized | deduplicated | replayable
        |
   +----+------------------+------------------+
   |                       |                  |
MULTIMODAL              AUTHENTICITY       LIVE / UTILITY
MATCHER                 EVIDENCE ENGINE    VERIFIER
classical +             Searcher           Searcher
optional donor
```

Workers may run concurrently. Only the campaign controller commits
authoritative state (Bible §8.3).

## Search loop (Bible §8.2)

```text
reference analysis
→ hypothesis portfolio
→ query portfolio
→ source plan
→ discovery
→ acquisition
→ normalization
→ cheap retrieval
→ fine verification
→ authenticity review
→ result routing
→ evidence-gap analysis
→ new query or next-evidence request
→ repeat until stop condition
```

The **served API process today** runs reference analysis and query
compilation, then stops with an honest `BLOCKED` because discovery is
not wired into that process. The later stages exist as packages and
tests. They are not invoked by `scripts/run_api.sh`. See
[docs/architecture/API.md](docs/architecture/API.md) and
[LIMITATIONS.md](LIMITATIONS.md).

## Waves in this tree

| Wave | What landed | Doc |
|---|---|---|
| 1 — constitution | contracts, budgets, evidence store, SQLite, campaign state machine, receipts, CLI | [docs/architecture/WAVE_1.md](docs/architecture/WAVE_1.md) |
| 2–3 — reference and query | upload hardening, unification, OCR, hypotheses, query families | [docs/architecture/REFERENCE_AND_QUERY.md](docs/architecture/REFERENCE_AND_QUERY.md) |
| discovery | robots-first HTTP, adapters, frontier, live check, optional Playwright | `src/searcher/sources/` |
| matching and authenticity | stages A–G, authenticity engine, two-bucket routing, ranking | [docs/architecture/MATCHING_AND_AUTHENTICITY.md](docs/architecture/MATCHING_AND_AUTHENTICITY.md) |
| API | FastAPI, SSE, deletion, capabilities probe | [docs/architecture/API.md](docs/architecture/API.md) |
| UI | dependency-free static `web/` | [web/README.md](web/README.md) |

`WAVE_1.md` is a constitution snapshot. Later waves added the rows
below it; that file was not rewritten to stay a snapshot.

## Module map

| Area | Path |
|---|---|
| Settings, ids, errors, budgets, capabilities | `src/searcher/core/` |
| §9 records, truth-law enums, three judgments | `src/searcher/contracts/` |
| Content-addressed store, lineage, quarantine | `src/searcher/evidence/` |
| SQLite WAL, migrations, repositories | `src/searcher/storage/` |
| State machine, controller, resume, events | `src/searcher/campaigns/` |
| Hash-chained receipts | `src/searcher/receipts/` |
| Upload, decode, OCR, views, signature | `src/searcher/reference/` |
| Portfolio, aliases, product codes | `src/searcher/hypotheses/` |
| Query families, languages, information gain | `src/searcher/queries/` |
| Adapters, robots, HTTP, frontier, live check | `src/searcher/sources/` |
| Dedup, listing clustering | `src/searcher/deduplication/` |
| Field / URL / size / currency | `src/searcher/normalization/` |
| Broad retrieve, embeddings hook (local weights only) | `src/searcher/retrieval/` |
| Classical match, parts, geometry, adjudicator | `src/searcher/matching/` |
| Construction, materials, logos, completeness | `src/searcher/authenticity/` |
| Two-tab routing, vetoes, monotonic rank | `src/searcher/ranking/` |
| SSRF, size limits | `src/searcher/security/` |
| FastAPI surface | `src/searcher/api/` |
| VisionMCP adapter (lazy, pin-checked) | `src/searcher/integrations/visionmcp/` |
| Job Scraper provenance (no donor import) | `src/searcher/integrations/job_scraper/` |

SQL lives in `migrations/`. Offline fixtures live in `fixtures/`.

## Donor boundary

**VisionMCP** is not vendored and is not in `pyproject.toml`. It is
pinned to SHA `18ee3c06d27f04937d1681dea5fa2650131e4b2a`
(`visionmcp-ocular` 0.8.0a2) and installed by
`scripts/setup_donor.sh` into `$SEARCHER_DONOR_DIR`. The adapter
lazy-imports a small surface and never imports `ocular`, `torch`,
`cv2`, or Playwright at probe time. Missing donor → honest
`unavailable`, `promotion_blocked` set. See
[docs/architecture/DONOR_SETUP.md](docs/architecture/DONOR_SETUP.md)
and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

**Job Scraper** is a frozen snapshot, not a git pin. Searcher ported
honest primitives (per-host pacing, robots cache, retry ceiling,
circuit breaker, work key, fetch log, live-status classification).
It rejected the §6.10 evasion surface (stealth, TLS impersonation,
UA rotation, proxy pools, persistent browser profiles). Provenance:
`$SEARCHER_JOBSCRAPER_FROZEN_DIR`, manifest digest `3a2c41c8…`.

**MTP** was not found. Searcher's own controller covers Bible §7.

## The three judgments

These stay separately typed. No path may substitute one for another.
Public gates read lower bounds.

| Judgment | Meaning |
|---|---|
| `ITEM_MATCH` | Is this the same physical model as the reference? |
| `AUTHENTICITY_CONFIDENCE` | Is the available evidence consistent with an authentic example? |
| `LISTING_UTILITY` | Is the listing live, reachable, and usable? |

Price may only pull authenticity down. A marketplace “authenticated”
badge is not proof. User text is a hypothesis (`USER_SUPPLIED`).
See `tests/unit/test_judgments.py`.

## Persistence

One SQLite database in WAL mode plus a content-addressed object
store. Campaign-private objects cannot be read across campaign ids.
Receipts verify by recomputation.

## Further reading

- [README.md](README.md) — how to run it
- [LIMITATIONS.md](LIMITATIONS.md) — what it does not claim
- [SECURITY.md](SECURITY.md) — threat model
- [PRIVACY.md](PRIVACY.md) — deletion and retention
- [CLAIMS.md](CLAIMS.md) — the sentences currently entitled
