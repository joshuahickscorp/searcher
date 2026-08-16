# API expectations (frontend)

The Bible specifies endpoints and event names, not every JSON field the
interface needs to draw a card, a compare view, or an honest empty state.
This file is the contract the UI actually consumes. The backend should
satisfy it. The development stub already does.

No field here is a secret. Numeric intervals are optional and are shown
only when developer numbers are enabled.

## Configuration

- `web/config.js` exports `API_BASE`.
- `?api=` on the page URL overrides it for local testing.
- The frontend never sends credentials.

## Endpoints used

```
POST   /v1/searches
GET    /v1/searches/{search_id}
GET    /v1/searches/{search_id}/events
GET    /v1/searches/{search_id}/results
GET    /v1/searches/{search_id}/results?bucket=real
GET    /v1/searches/{search_id}/results?bucket=possibly_real
GET    /v1/results/{result_id}
POST   /v1/searches/{search_id}/cancel
DELETE /v1/searches/{search_id}
GET    /v1/capabilities
GET    /v1/health
```

`POST /v1/searches/{id}/refresh` and `POST /v1/results/{id}/feedback` are
recognized by the stub and unused by the first UI.

## `POST /v1/searches`

`multipart/form-data` fields (repeated names, not `images[]` brackets):

| field | required | notes |
| --- | --- | --- |
| `images` | yes, 1–10 | one part per file |
| `text` | no | free text |
| `tags` | no | one part per tag |
| `client_search_id` | no | idempotency key |

The UI also accepts the Bible’s `images[]` / `tags[]` names if the server
prefers them.

Success body:

```json
{
  "search_id": "uuid",
  "state": "CREATED",
  "events_url": "/v1/searches/{id}/events",
  "results_url": "/v1/searches/{id}/results"
}
```

Validation errors use HTTP 422 and `{ "error": "...", "detail": "human text" }`.
The server is the authority; the UI’s 1–10 / type / size checks are courtesy.

## `GET /v1/searches/{id}`

```json
{
  "search_id": "uuid",
  "state": "RANKING",
  "state_version": 8,
  "terminal_status": "COMPLETE",
  "terminal_reason": "human text",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "progress": { "stage": "Ranking results", "detail": null },
  "coverage": {
    "sources_completed": [{ "id": "", "name": "", "status": "", "detail": "" }],
    "sources_blocked": [{ "id": "", "name": "", "status": "", "detail": "" }],
    "sources_in_progress": [],
    "pages_fetched": 0,
    "candidates_normalized": 0,
    "candidates_hidden": 0
  },
  "counts": { "real": 0, "possibly_real": 0, "hidden": 0 },
  "hidden_policy_note": "Some candidates did not meet policy.",
  "missing_reference_views": [{ "view": "sole", "why": "..." }],
  "deeper_refresh_available": true,
  "intent": { "text": "", "tags": [] }
}
```

`progress.stage` must be one of the §24.4 phrases when present. The UI
can map a raw `state` to those phrases if `stage` is missing.

`terminal_status` is one of `COMPLETE | PARTIAL | BLOCKED | FAILED | CANCELLED`
or `null` while running.

404 means the search is gone. The UI says it was deleted. It does not
say “no results.”

## SSE `GET /v1/searches/{id}/events`

Event names are exactly those in Bible §25.4. Payloads:

| event | data |
| --- | --- |
| `search.state` | `{ "state", "version" }` |
| `search.progress` | `{ "stage", "detail" }` |
| `search.coverage` | same object as `coverage` above |
| `candidate.discovered` | `{ "candidate_id" }` (UI ignores extras) |
| `candidate.normalized` | `{ "candidate_id" }` |
| `candidate.promoted` | `{ "candidate_id" }` |
| `candidate.updated` | `{ "candidate_id" }` |
| `result.real` | a result object (see below) |
| `result.possibly_real` | a result object |
| `result.removed` | `{ "result_id", "reason" }` |
| `search.warning` | `{ "code", "message" }` |
| `search.complete` | `{ "terminal_status", "reason" }` |

Events should carry `id:` so `Last-Event-ID` can resume. Already-emitted
events may be replayed; the UI upserts by `result_id` and does not steal
focus.

## Result object

Used by `result.real` / `result.possibly_real`, `GET .../results`, and
`GET /v1/results/{id}`. Compare and “Why this result” may be omitted from
the stream and filled by `GET /v1/results/{id}`.

```json
{
  "result_id": "uuid",
  "search_id": "uuid",
  "candidate_id": "uuid",
  "bucket": "real",
  "rank": 1,
  "title": "untrusted string",
  "source": { "name": "untrusted string", "adapter": "public_html" },
  "listing_url": "https://...",
  "primary_image": { "url": "https://... or /path", "alt": "untrusted string" },
  "price": { "original": "128000", "currency": "JPY", "display": "¥128,000" },
  "size": { "marked": "42", "system": "EU", "display": "Size 42" },
  "availability": "LIVE",
  "last_checked_at": "ISO-8601",
  "item_match": { "label": "High", "mean": 0.94, "lower_bound": 0.91, "upper_bound": 0.97 },
  "authenticity": { "label": "High", "mean": 0.86, "lower_bound": 0.81, "upper_bound": 0.91 },
  "listing_utility": { "live": true, "label": "Live", "score": 0.88, "last_checked_at": "ISO-8601" },
  "evidence_chips": [{ "kind": "support", "text": "panel geometry" }],
  "primary_gap": { "kind": "missing", "text": "tongue label not shown" },
  "why": {
    "heading": "Why Real",
    "points": ["..."],
    "tab_reason": "...",
    "still_unverified": ["No physical inspection."],
    "supporting": ["..."],
    "contradictions": [],
    "missing": ["..."],
    "seller_reported": [{ "field": "Size", "value": "42", "origin": "REPORTED_BY_SELLER" }],
    "images_compared": [{ "role": "user_reference", "url": "", "alt": "" }],
    "duplicate_image_family_count": 0,
    "live": true,
    "checked_at": "ISO-8601"
  },
  "compare": {
    "reference_crop": { "url": "", "alt": "", "part": "lateral panel" },
    "candidate_crop": { "url": "", "alt": "", "part": "lateral panel" },
    "parts": [{ "part": "", "status": "", "note": "", "origin": "OBSERVED" }],
    "supporting": [],
    "contradictions": [],
    "missing_views": [],
    "seller_reported_fields": [{ "field": "", "value": "", "origin": "REPORTED_BY_SELLER" }]
  }
}
```

### Labels

`item_match.label` and `authenticity.label` are words, never a percentage
in the default UI:

`High` | `Moderate` | `Incomplete evidence` | `Contradictory`

`listing_utility` is a third, separate thing. Do not merge the three.

`availability` is `LIVE | SOLD | RESERVED | REMOVED | UNKNOWN`.
Only `LIVE` listings get an “Open listing” action.

`evidence_chips[].kind` is `support | missing | contradiction`.
`primary_gap.kind` is `missing | contradiction`.
`origin` uses the §3.1 vocabulary (`OBSERVED`, `REPORTED_BY_SELLER`, …).

### Untrusted strings and URLs

Titles, source names, alt text, seller fields, chip text, and descriptions
are attacker-controlled. The UI inserts them as text.

`listing_url` must be absolute `http` or `https`. Any other scheme is
refused and no outbound control is rendered.

Image URLs may be absolute `http`/`https` or a root-relative path on the
API origin. `javascript:`, `data:`, and `file:` image URLs are refused.

## `GET /v1/searches/{id}/results`

Without `bucket`:

```json
{
  "search_id": "uuid",
  "real": [/* result objects */],
  "possibly_real": [/* result objects */],
  "counts": { "real": 0, "possibly_real": 0, "hidden": 0 }
}
```

With `bucket=real` or `bucket=possibly_real`:

```json
{ "search_id": "uuid", "bucket": "real", "results": [] }
```

## `GET /v1/health`

```json
{ "status": "ok" }
```

Any network failure or non-OK response is treated as API unavailable.

## `GET /v1/capabilities`

Informational. The UI does not require it to search. Useful fields:

```json
{
  "api_version": "v1",
  "max_images": 10,
  "min_images": 1,
  "accepted_media_types": ["image/jpeg", "image/png", "image/webp", "image/gif"]
}
```

## Honesty rules the API must enable

- A `BLOCKED` or `FAILED` campaign must not be shaped like an empty
  successful search. `terminal_status` and `terminal_reason` are required.
- If candidates were hidden, send `counts.hidden` and/or
  `hidden_policy_note`. The UI will only say that some candidates did not
  meet policy.
- If no displayable candidate exists, still send coverage, blocked
  sources, missing reference views, and whether a deeper refresh exists.
- Every public result should be able to answer the §3.10 questions via
  `why` and `compare`. If a question cannot be answered, omit the field;
  the UI will say the service did not provide it.
