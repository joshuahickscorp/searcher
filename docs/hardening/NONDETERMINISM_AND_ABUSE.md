# Offline campaign nondeterminism and the abuse suite

## FAILED versus BLOCKED

The same offline campaign sometimes ended `FAILED` and sometimes `BLOCKED`.
The cause was not the reference pipeline and not a mapped verdict.

`Database.execute()` returned a live `sqlite3.Cursor` and dropped the process
write lock before the caller fetched rows. `sqlite3.Row` aliases the statement.
A second thread (SSE reader or another write) reset that statement, so
`fetchone()` returned a row whose `intent_json` was `NULL`.

Observed 2026-08-16 on this host, `SEARCHER_FAIL_TRACE` set:

```text
TypeError: the JSON object must be str, bytes or bytearray, not NoneType
  run_api_campaign
    run_reference_query_wave
      controller.transition
        repos.get_campaign
          _campaign_from_row
            json.loads(row["intent_json"])   # intent_json was None
```

A standalone concurrent SELECT / UPDATE on the same connection reproduced
`intent_json=None` within 1.5 seconds.

`FAILED` was the generic `except Exception` path. The error was not recorded
on the campaign. The SSE test also drained the stream when
`campaign_is_closed` became true after the `BLOCKED`/`FAILED` state event and
before `search.complete` was appended (`src/searcher/api/events.py` lines
55–58; owned by the API lane).

### Fix

- `Database.execute()` copies every row into a `SnapshotRow` before releasing
  the lock (`src/searcher/storage/connection.py`).
- A genuine internal error is sealed as `FAILED` with a
  `CampaignTerminalReceipt` and the exception class on the event `error`
  field. Input, decode, budget, and storage-pressure stops are `BLOCKED`
  with a stated reason.
- The flaky test waits for the `search.complete` event instead of assuming
  the stream stays open until the campaign finishes.

`src/searcher/api/events.py` still closes the stream when the campaign is
terminal even if `search.complete` has not been written yet. This lane cannot
edit that file.

Concurrent creates of the same image bytes also raced in
`ContentStore.link_zone` / `object_index.json` (not in this lane). The API
worker serializes ingest and the reference wave on a process lock so that
race cannot return HTTP 500.

## Soak

`scripts/soak_api.sh` and `tests/real_runtime/test_api_soak.py` run fifty
sequential offline searches against a locally spawned API and write
`artifacts/hardening/soak.json`.

Measured 2026-08-16, this host, fifty sequential offline searches:

| | RSS (KB) | FDs | SQLite bytes |
|---|---|---|---|
| before | 69952 | 15 | 4096 |
| after 1 | 84384 | 16 | 4096 |
| after 25 | 88192 | 16 | 2043904 |
| after 50 | 89008 | 16 | 3702784 |

RSS rose ~19 MB in the first search (import/warm) and then 4.6 MB across the
remaining 49. FDs stayed at 16 after the first search. Database growth is
proportional to retained campaign rows (~74 KiB each), not a per-request leak.

## Abuse

`tests/real_runtime/test_api_abuse.py` drives a loopback process. The case
table is written to `artifacts/hardening/abuse-table.json`.
