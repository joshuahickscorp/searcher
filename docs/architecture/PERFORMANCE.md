# Performance

Searcher is a live campaign. It plans queries, fetches admitted sources under
robots and rate policy, normalizes, clusters, matches, and checks liveness.
A precomputed image index answers a lookup against work that already happened.
Those are different operations. A cold live campaign cannot equal an index
lookup, and this tree does not pretend otherwise.

What can be genuinely fast:

1. The interface always responds immediately. `POST /v1/searches` returns
   without waiting for analysis.
2. First evidence can appear as soon as a candidate exists, including from
   the warm index, streamed over SSE.
3. Repeat and overlapping searches are served from a warm local index so the
   same source work is not done twice.

## Warm index

`searcher.index` persists public listing work: normalized candidates, canonical
URLs, cluster membership, image digests and perceptual hashes, derived
descriptors, and last-known live status with `last_checked_at`.

It also holds:

- an inverted text index over titles, descriptions, and OCR terms;
- a compact descriptor index (hashed text vectors and colour histograms)
  stored as SQLite blobs and scored with numpy. There is no vector database.

Cache keys follow Bible §27.5: content digest, adapter version, model version,
parameters, schema version, policy version. Changing any component misses
rather than serving a stale answer under a new policy.

Live status older than `SEARCHER_LIVENESS_TTL_SECONDS` (default six hours) is
shown as unverified (`UNKNOWN`), never as `LIVE`. `last_checked_at` is kept.
A background or later live-check stage may refresh it; the index does not
invent a live bit.

Inhibition of return (§22.4) is durable: a query already run against a source
with unchanged versions is not run again. Content that changed, a new
hypothesis, or a version bump is a reason to run it.

The index is a cache of work, never a shortcut around the truth gates. An
index hit copies stored evidence intervals exactly and re-routes. It does not
raise a lower bound. Campaign-private artifacts (user uploads, private object
store paths) are refused. One campaign cannot read another’s private bytes
through the index. Shared rows are policy-permitted derived artifacts of
public listings, and they survive campaign delete.

## Measured targets

Engineering targets, subject to a baseline on this host
(`artifacts/searcher-performance.receipt.json`):

```text
UI first byte                 < 200 ms
search creation response      < 300 ms
first progress event          < 500 ms
first candidate on screen     < 3 s   (warm)
repeat/overlapping search     < 1 s   to first result
health                        < 50 ms
capabilities                  < 100 ms
```

`scripts/bench_latency.sh` measures them. It does not tune the system to
make the number pass. A measured miss is the useful result.

HTTP numbers in the receipt are taken against the real FastAPI app on this
host via Starlette TestClient when a kernel TCP bind is not available.
Fixture numbers are the campaign path that actually produces candidates and
routed results, cold then warm, with cost receipts.

## What was slow, and what changed

Profile first. On this host a `json_group_array` rewrite of `get_campaign`'s
child-id lists was *slower* than the original six primary-key selects
(tiny rows, correlated subqueries). That change was reverted. What did
pay: `emit()` used to call `get_campaign` on every public event. It now
reads only `state_version`. The receipt records 200-iteration times for
both. `open_rgb` re-decoded the same PNG on every cheap-signal call; an
LRU keyed by content digest serves the repeat. Unique images still decode.

Robots were already cached per origin with a TTL. Admission consults that
cache before fetching. That path was not changed.

Budgets stay sealed. Per-host rate policy and robots stay authoritative. No
stage is skipped to make a number look good. IOR skips *duplicate source
work*, not ranking, not live-check, not truth gates.

## Cost receipts

Each consult and remember writes a `CostReceipt` with `payload.phase`,
`payload.fetches`, and `cache_hits`. A repeat overlapping fixture search
should show fetches on the first campaign and cache hits, zero fetches on the
second. That is the proof the index did the work.

## How to re-measure

```text
bash scripts/bench_latency.sh
```

Writes `artifacts/searcher-performance.receipt.json`. Compare that file, not
adjectives.
