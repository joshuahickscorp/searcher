# Wave 1 — what exists

Wave 1 is the Searcher constitution. It is the typed surface later waves
implement against.

## Present

- `searcher.core` — settings, ids, UTC time, §30.3 errors, sealed budgets,
  capability registry, provisional §20.2/§20.3 gates.
- `searcher.contracts` — every §9 record, the truth-law enums, the three
  independent judgments, degraded-path labels, routing guards.
- `searcher.evidence` — immutable records, lineage, content-addressed store
  with §27.3 zones, quarantine, promotion, independent-family counting.
- `searcher.storage` — WAL SQLite, numbered SQL migrations, typed repositories,
  optimistic `state_version`.
- `searcher.campaigns` — §10.1 state machine, §10.2 guards, single-writer
  controller, checkpoints, resume reconstruction, cancellation, append-only
  events with §25.4 names.
- `searcher.receipts` — hash-chained receipts that `verify()` by recomputation.
- `searcher` CLI — create/run/show/events/resume/cancel/budget, receipt verify,
  store stat, db migrate.
- `fixtures/dior_minimal` — fully offline fixture campaign.

## Guarantees

- Seller-reported values cannot be constructed as `OBSERVED`.
- `ITEM_MATCH`, `AUTHENTICITY_CONFIDENCE`, and `LISTING_UTILITY` are distinct types.
- Public gates read score lower bounds.
- Fallback paths cannot emit `REAL` / `AUTHENTICATED` / `VERIFIED_GENUINE` /
  `EXHAUSTIVE_SEARCH_COMPLETE`.
- A sealed budget cannot be exceeded.
- Only `CampaignController` commits campaign state.
- Crash-resume reconstructs hypotheses, queries, cursors, pages, candidates,
  budget, results, and accepted evidence.

## Deliberately absent until a later wave

- Network, source adapters, HTTP, browsers.
- Vision, image decoding, OCR, embeddings, VisionMCP calls.
- FastAPI, SSE, frontend.
- Matching, ranking, and authenticity *algorithms* (containers and gates only).
- Query compiler and hypothesis inference logic beyond the data model.
- Docker, CI workflows, deployment config.
