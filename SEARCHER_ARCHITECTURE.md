# Searcher architecture

Bible §39 name. Draws from `ARCHITECTURE.md` and
`docs/architecture/`. The standing design is Bible §8. This file
states what the tree at
`31e6004c76e1d845447e0993a5ce68948f311265` implements.

## Graph

```text
WEB APP  (web/)
  images | text | tags | progress | Real | Possibly Real | Replica
        |
API GATEWAY  (src/searcher/api/)
        |
SEARCH CAMPAIGN CONTROLLER  (src/searcher/campaigns/)
        |
REFERENCE → HYPOTHESIS & QUERY → SOURCE BROKER → RESULT PUBLISHER
        |
CANDIDATE + EVIDENCE STORE
        |
MULTIMODAL MATCHER | AUTHENTICITY ENGINE | LIVE / UTILITY VERIFIER
```

Workers may run concurrently. Only the campaign controller commits
authoritative state (Bible §8.3).

The served API runs the campaign orchestrator when
`SEARCHER_LIVE_DISCOVERY=1`, the default in `scripts/run_api.sh`.
A campaign that planned no source work, compiled no usable query, or
fetched nothing stops `BLOCKED` and names what was missing.
`COMPLETE` means planned coverage was searched and exhausted.
`PARTIAL` is the common live outcome.

Source names on the live path are derived from the adapter registry:
every admitted, enabled, credential-free source, in
`searcher.sources.broker.DEFAULT_ORDER`. See
`src/searcher/workers/api_campaign.py:uncredentialed_source_names`.
That is ten names at this SHA. eBay and Etsy are omitted because they
cannot answer without an operator key.

## Packages

See `docs/architecture/MODULE_MAP.md` for the path table. The
distribution is `src/searcher/`.

| Area | Path | Further reading |
|---|---|---|
| Settings, budgets, capabilities | `src/searcher/core/` | |
| §9 records and three judgments | `src/searcher/contracts/` | `SEARCHER_DATA_MODEL.md` |
| Content-addressed store | `src/searcher/evidence/` | |
| SQLite WAL | `src/searcher/storage/` | |
| State machine, resume | `src/searcher/campaigns/` | `docs/architecture/ORCHESTRATION.md` |
| Receipts | `src/searcher/receipts/` | |
| Upload, OCR, views | `src/searcher/reference/` | `docs/architecture/REFERENCE_AND_QUERY.md` |
| Hypotheses, queries | `src/searcher/hypotheses/`, `src/searcher/queries/` | same |
| Adapters, robots, frontier | `src/searcher/sources/` | `SEARCHER_SOURCE_POLICY.md` |
| Matching and authenticity | `src/searcher/matching/`, `src/searcher/authenticity/` | `docs/architecture/MATCHING_AND_AUTHENTICITY.md` |
| Two-tab routing | `src/searcher/ranking/` | `SEARCHER_BUCKET_POLICY.md` |
| SSRF, size limits | `src/searcher/security/` | `SEARCHER_SECURITY.md` |
| FastAPI | `src/searcher/api/` | `docs/architecture/API.md` |
| Static UI | `web/` | `SEARCHER_UX_SPEC.md`, `docs/architecture/SERVING.md` |
| VisionMCP adapter | `src/searcher/integrations/visionmcp/` | `docs/architecture/DONOR_SETUP.md` |
| Job Scraper provenance | `src/searcher/integrations/job_scraper/` | no donor import |

## Three judgments

Separately typed. Public gates read lower bounds.

| Judgment | Meaning |
|---|---|
| `ITEM_MATCH` | Same physical model as the reference? |
| `AUTHENTICITY_CONFIDENCE` | Is available evidence consistent with an authentic example? |
| `LISTING_UTILITY` | Live, reachable, usable? |

Price may only pull authenticity down. A marketplace badge is not
proof. User text is a hypothesis.

## Donor boundary

- **VisionMCP** is not vendored. Pin
  `18ee3c06d27f04937d1681dea5fa2650131e4b2a`. Missing donor →
  unavailable.
- **Job Scraper** is a frozen snapshot, not a git pin. Honest
  primitives were reimplemented. The §6.10 evasion surface is
  rejected (`tests/unit/test_donor_rejection.py`).
- **MTP** was not found.

## Persistence

One SQLite database in WAL mode plus a content-addressed object
store. Campaign-private objects cannot be read across campaign ids.
Receipts verify by recomputation.

## What is not established

- A module-level “wave complete” map beyond the rows in
  `ARCHITECTURE.md`. `docs/architecture/WAVE_1.md` is a constitution
  snapshot and was not rewritten as later waves landed.
- That every Bible §35 file exists under the Bible's proposed path.
  The tree uses the package layout above.
