# Searcher HTTP API

Local, unauthenticated first alpha. One process, FastAPI, SQLite WAL, asyncio
HTTP, campaign work on a background thread. The campaign controller is the only
writer of campaign state.

Start:

```text
scripts/run_api.sh
# or
uv run searcher serve --static
```

Default bind is `127.0.0.1:8765`. `--static` (also the script default) mounts
`web/` for local use only so `web/config.js` can keep `API_BASE = ""`.

Environment:

| variable | default | purpose |
|---|---|---|
| `SEARCHER_API_HOST` | `127.0.0.1` | bind address |
| `SEARCHER_API_PORT` | `8765` | bind port |
| `SEARCHER_DATA_ROOT` | `data` | SQLite + object store |
| `SEARCHER_CORS_ORIGINS` | localhost dev origins | comma-separated allow list; `*` is ignored |
| `SEARCHER_SERVE_WEB` | `0` (`1` in `run_api.sh`) | DEV ONLY static mount |
| `SEARCHER_LIVE_DISCOVERY` | `1` (`1` in `run_api.sh`) | run live listing discovery from the API process |
| `SEARCHER_EMBEDDING_WEIGHTS` | unset | path to a local DINOv2 ViT-S/14 TorchScript file; loaded lazily on the first successful probe / embed, never downloaded |
| `SEARCHER_MAX_IMAGES` | `10` | per-search image cap |
| `SEARCHER_MAX_UPLOAD_BYTES` | 15 MiB | per-file cap |
| `SEARCHER_MAX_TOTAL_UPLOAD_BYTES` | 50 MiB | combined upload cap |

CORS never pairs credentials with a wildcard origin. The frontend does not send
credentials.

## Endpoints

Errors are `{ "error": "<code>", "detail": "<human text>" }`. Hostile input is
`422` / `415` / `400`, never `500`. `404` means the search or result is gone
(including after delete). The UI treats that as deleted, not as “no results.”

### `POST /v1/searches`

`multipart/form-data`. Field names `images` / `images[]`, `text`, `tags` /
`tags[]`, `client_search_id`, `source_scopes` / `source_scopes[]` (repeated
`legitimate` and/or `replica`; unknown values ignored; absent defaults to
`legitimate`).

Returns immediately (`201`) without waiting for analysis:

```json
{
  "search_id": "uuid",
  "state": "CREATED",
  "events_url": "/v1/searches/{id}/events",
  "results_url": "/v1/searches/{id}/results"
}
```

`client_search_id` is idempotent: the same key returns the existing campaign
(`200`) instead of starting a second one. After delete the key may be reused.

Uploads go through `searcher.reference.validation` (magic bytes, dimension and
decompression limits, path-name refusal) and `searcher.reference.ingest`
(content-digest store). Declared filenames never become filesystem paths.

### `GET /v1/searches/{search_id}`

Campaign projection consumed by `web/`. `terminal_status` is one of
`COMPLETE | PARTIAL | BLOCKED | FAILED | CANCELLED` or `null` while running.
It is copied verbatim from the controller. An empty result list is never
substituted for blocked or failed.

`progress.stage` uses the §24.4 phrases. `coverage` uses the frontend object
(`sources_completed`, `sources_blocked`, `pages_fetched`, …).

### `GET /v1/searches/{search_id}/events`

Server-Sent Events. Event names are exactly §25.4:

```text
search.state
search.progress
search.coverage
candidate.discovered
candidate.normalized
candidate.promoted
candidate.updated
result.real
result.possibly_real
result.replica
result.removed
search.warning
search.complete
```

`id:` is a campaign-local monotonic integer. Reconnect with `Last-Event-ID`
replays `id > last` from the append-only log: no gap, no duplicate. Heartbeats
are SSE comments (`: heartbeat`) so proxies do not idle the connection out.
The stream closes on a terminal campaign after the remaining events are sent,
and on client disconnect.

Payloads match `web/API_EXPECTATIONS.md`. `search.complete` is
`{ "terminal_status", "reason" }`. `result.real` / `result.possibly_real` /
`result.replica` carry a result object when one has been stored. This process
does not invent those events. A replica result is never merged into Real or
Possibly Real.

### `GET /v1/searches/{search_id}/results`

Without `bucket`: `{ search_id, real, possibly_real, counts }` and `replica`
when that list is non-empty.

With `?bucket=real`, `?bucket=possibly_real`, or `?bucket=replica`:
`{ search_id, bucket, results }`.

Hidden / rejected candidates are not listed. If routing has not run, both
lists are empty and `GET /v1/searches/{id}` tells the truth about why.

### `GET /v1/results/{result_id}`

One public result. Same object as the stream / list. `404` if missing or the
parent search was deleted.

### `POST /v1/searches/{search_id}/refresh`

`202`. Re-verifies availability, price, size, and destination only when a
sources-layer live check exists. This process does not fetch user-supplied
URLs. It records a `LiveCheckReceipt` and a `search.warning` when refresh
cannot run, and it does not fabricate a new `last_checked_at`.

### `POST /v1/searches/{search_id}/cancel`

Stops new work, marks unfinished tasks cancelled, persists `CANCELLED`, keeps
already produced evidence, emits `search.complete`.

### `POST /v1/results/{result_id}/feedback`

JSON `{ "verdict": "<§22.5 name>", "note": "optional" }`. Verdicts:

`correct_item`, `wrong_model`, `likely_real`, `uncertain`,
`likely_counterfeit`, `listing_dead`, `duplicate`, `useful_result`.

Stored as a signed local evidence record plus a `FeedbackReceipt`. It does not
promote, demote, or train anything.

### `DELETE /v1/searches/{search_id}`

`204`, then subsequent reads are `404`. Removes campaign-private objects,
events, candidates, results, and user text. Retains receipts (including the
`DeletionReceipt`) and any shared content-addressed object still owned by
another campaign. The receipt states both lists.

### `GET /v1/capabilities`

Real millisecond probe. Includes `max_images`, `accepted_media_types`, lane
records, `blocked_lanes` with reasons, donor status, and honest
`discovery` / `routing` availability.

### `GET /v1/health`

Cheap liveness. `SELECT 1` against SQLite. No model load, no browser,
no donor import. Body includes `status` (`ok` or `degraded`), `api`,
`db`, `lanes`, and `blocked_lanes`. See
[SERVING.md](SERVING.md).

## SSE reconnection

1. Client stores the last seen `id:`.
2. On drop, it reconnects with `Last-Event-ID`.
3. The server emits only later public events, in log order.

Invalid `Last-Event-ID` is treated as `0` (full replay). Already-emitted
events may be replayed if the client omits the header; the UI upserts by
`result_id`.

## Honest degradation

| condition | campaign | results | capabilities |
|---|---|---|---|
| Donor absent / incompatible | Reference analysis still runs via Pillow; visual donor lanes stay blocked | No Real promotion through a fallback | `blocked_lanes` lists why |
| Discovery absent or `SEARCHER_LIVE_DISCOVERY=0` | Terminal `BLOCKED` after the reference/query wave | Empty public lists | `discovery.available = false` (or disabled) |
| Discovery present (default `run_api.sh`) | Orchestrator runs; `COMPLETE` only after planned coverage was searched and exhausted; zero fetches is `BLOCKED` naming what was missing; otherwise `PARTIAL` / `BLOCKED` from coverage | Public lists may be empty; hidden candidates are not shown | `discovery.available = true` |
| Routing / ranking absent (this process) | Same: no invented bucket | Empty public lists unless another writer stored a decision | `routing.available = false` |
| Refresh without sources | `202`, `search.warning` | `last_checked_at` unchanged | — |
| Cancel | `CANCELLED` | Evidence retained | — |
| Delete | `404` | `404` | — |

A `BLOCKED` or `FAILED` campaign is never shaped like an empty successful
search. `search.complete` is an SSE name; it is not an
`EXHAUSTIVE_SEARCH_COMPLETE` claim.

## Security notes

- The API never fetches a user-supplied URL.
- User strings never become filesystem paths; artifacts are addressed by digest.
- One campaign cannot read another campaign’s events, results, or private
  artifacts.
- Listing strings leave the API as JSON data, never HTML.
- Structured logs carry a request id, method, a sanitized path, status, and
  duration. They do not carry upload bytes, filenames, private paths, secrets,
  or listing bodies.
