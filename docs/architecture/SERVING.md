# Serving Searcher so other people can use it

The owner runs the API on their Mac. Friends use the static GitHub Pages UI
against that API. The engine is a live campaign, not a hosted product.

There is no authentication in this alpha. Treat every non-loopback URL as
public to whoever has it.

## Is it live?

**Yes, live:** `scripts/serve_shared.sh` is still running, and

```text
GET /v1/health
```

returns HTTP 200. `status` is `"ok"` or `"degraded"`. `api` is `"up"`.

**Not live:** the process is not running, the laptop is asleep or offline, or
the health fetch fails. Tell friends it is down. There is no queue and no
retry on their side that will wake the Mac.

`status=ok` means the API process and SQLite answered. `status=degraded` means
the API is up but a named lane in `blocked_lanes` is not. A failed fetch is
not this document — it is “API unreachable.”

Do not use `/v1/capabilities` as the liveness probe. That endpoint probes
lanes and is allowed to be slower.

## Health contract (for the Pages UI)

`GET /v1/health` is cheap: `SELECT 1`, an index row count, no model load, no
browser, no donor import. CORS is whatever `SEARCHER_CORS_ORIGINS` is for
this process.

```json
{
  "status": "ok",
  "api": "up",
  "db": "ok",
  "checked_at": "2026-08-16T00:00:00+00:00",
  "lanes": {
    "storage": { "ok": true },
    "index": { "ok": true, "entries": 0 },
    "discovery": { "ok": true, "reason": "..." },
    "vision": { "ok": true, "reason": "not probed on /v1/health; see GET /v1/capabilities" }
  },
  "blocked_lanes": []
}
```

How the UI should read it:

| What the browser sees | Meaning |
|---|---|
| fetch failed / network error | API unreachable. Show offline. |
| HTTP 200, `status=ok` | API up, no blocked lane reported here. |
| HTTP 200, `status=degraded` | API up, `blocked_lanes` lists what is not usable. |

`status` stays `"ok"` or `"degraded"` so an older client that only checks
`status === "ok"` still works for the healthy case.

## One command

```text
scripts/serve_shared.sh
```

Binds `127.0.0.1:8765` by default. Serves `web/` for local use. Prints the
`?api=` URL to hand to a friend (they still cannot reach loopback on your
Mac — this mode is for you).

```text
scripts/serve_shared.sh --lan
```

Binds the Mac’s LAN address and prints that URL. Same network only.

```text
scripts/serve_shared.sh --tunnel
```

Uses `cloudflared` **if it is already installed**. Prints the public URL.
If `cloudflared` is missing, the script refuses and tells you so. It does
not install anything, create an account, or sign anyone up.

`--lan` and `--tunnel` are opt-in. Off by default.

## CORS

CORS is taken from the mode, not widened in the process defaults.
`SEARCHER_CORS_ORIGINS` is an allowlist. An origin that is not on it is
refused, which the interface reports as “The search service is unavailable.”

- Local: loopback origins used by the local UI (ports 8765, 8080, 8000).
- LAN: those plus `http://<lan-ip>:<port>`.
- Any mode: set `SEARCHER_PAGES_ORIGIN` to the Pages **origin**
  (`https://joshuahickscorp.github.io`, no `/searcher` path) so the
  published page is allowed to call the API.

`SEARCHER_PAGES_URL` is the full page URL printed for friends
(`https://joshuahickscorp.github.io/searcher/`). It is not a CORS
origin. The script default is a placeholder until you set it.

`*` is ignored by the settings parser. Credentials are never paired with a
wildcard.

## What to send a friend

Send the printed **API origin** for loopback and LAN. That origin also
serves `web/`, so the browser stays on one scheme and one host.

The printed Pages `?api=` line is only usable when the API origin is
HTTPS (the tunnel) **and** `SEARCHER_PAGES_ORIGIN` is on the allowlist:

```text
https://joshuahickscorp.github.io/searcher/?api=https://<tunnel>
```

Do not point the published HTTPS page at `http://127.0.0.1` or at a
LAN `http://` address. Browsers refuse that combination (mixed content
and private-network access). The page then looks as if the service is
down. Local troubleshooting uses the local copy of the interface.

When you start the server, tell them it is live. When you stop it, tell
them it is not. Health is the machine check; a text is the human one.

Operator steps: [docs/OPERATING.md](../OPERATING.md).

## What this is not

It is not a hosted service. It is not authenticated. A tunnel URL is not a
secret. Stopping the process is how you take it down. A search can
honestly return nothing. The process is not reachable while the machine
is asleep.
