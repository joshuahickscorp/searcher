# Operating Searcher

How to run the engine on your computer, share it, and tear it down.
The public page is only the interface. This file is the operator
manual; [README.md](../README.md) is the front door.

## What this alpha does not do

- **No authentication.** Anyone who can reach the API can create
  searches, read results, and cancel or delete campaigns.
- **No hosted backend.** GitHub Pages does not run Searcher. A visitor
  who opens the published page while your process is down sees
  “The search service is unavailable.”
- **No reachability while you are away.** Results exist only while
  your computer is awake and the script is running. Sleep, quit, or
  a network drop takes it down. There is no queue that will wake it.
- **No guaranteed hits.** A finished search can honestly return
  nothing in Real and Possibly Real. Hidden candidates are not shown.
  That is not a finding that the item does not exist.

## Prerequisites

[uv](https://docs.astral.sh/uv/). The project pins Python 3.13 in
`.python-version`. `uv sync` uses that interpreter; your default
`python3` can be something else.

## Run locally

```bash
git clone https://github.com/joshuahickscorp/searcher.git
cd searcher
uv sync
./scripts/run_api.sh
```

Open http://127.0.0.1:8765/

That command binds loopback, serves `web/` from the same origin, and
writes under `data/` in the clone. Live listing discovery is on
(`SEARCHER_LIVE_DISCOVERY=1`).

If the port is already taken the process exits with `address already
in use`. Pick another port:

```bash
SEARCHER_API_PORT=8766 ./scripts/run_api.sh
```

Then open http://127.0.0.1:8766/

Use this local copy of the interface for local work. Do **not** open
https://joshuahickscorp.github.io/searcher/?api=http://127.0.0.1:8765
— that is an HTTPS page calling a private HTTP origin. Browsers
refuse it (mixed content and private-network access). The page then
says the search service is unavailable even when the process is up.

### Is it up?

```bash
curl -sS http://127.0.0.1:8765/v1/health
```

Substitute the port you chose. HTTP 200 with `"status": "ok"` or
`"degraded"` means the process answered. A failed fetch means it is
down. Do not use `/v1/capabilities` as the liveness probe.

On a clean clone, `GET /v1/capabilities` reports
`discovery.available = true` and `routing.available = true` when
those packages imported. Donor-backed visual lanes stay blocked
until the optional donor is installed. Learned embeddings stay
blocked when no local weights are present.

### First search

The form at `/` is the interface. One image is enough. You can also
POST (substitute the port if you overrode it):

```bash
curl -sS \
  -F "images=@fixtures/images/trainer_a.png;type=image/png" \
  -F "text=Dior Homme General Army Trainer 07" \
  -F "tags=footwear" \
  http://127.0.0.1:8765/v1/searches
```

Then `GET /v1/searches/{search_id}` until `terminal_status` is set.
`COMPLETE`, `PARTIAL`, and `BLOCKED` are all finished. Empty `real`
and `possibly_real` lists are allowed. `counts.hidden` and
`hidden_policy_note` are how hidden candidates are acknowledged.

A first live search can take a couple of minutes. eBay reports
`AUTH_REQUIRED` unless `EBAY_API_KEY` is set. Other admitted sources
are tried without keys. Some sources can be `SOURCE_UNAVAILABLE`.
A blocked source is recorded as blocked, never as “searched, nothing
found.”

## Share with a friend

`scripts/serve_shared.sh` is the sharing entry point.

```bash
./scripts/serve_shared.sh --help
```

The script always prints this warning, and the warning is the truth:

```text
WARNING: This alpha has no authentication.
Whoever can reach the printed URL can create searches, read results,
and cancel or delete campaigns. --lan and --tunnel are opt-in.
```

`--lan` and `--tunnel` expose that unauthenticated API to whoever
has the URL. Do not treat a tunnel URL as private.

Set these so the printed Pages link is the real site and the Pages
origin is allowed through CORS:

```bash
export SEARCHER_PAGES_URL=https://joshuahickscorp.github.io/searcher/
export SEARCHER_PAGES_ORIGIN=https://joshuahickscorp.github.io
```

`SEARCHER_PAGES_ORIGIN` is the origin only (scheme + host). It does
**not** include `/searcher/`.

`SEARCHER_CORS_ORIGINS` is an allowlist. A page served from an
origin that is not on it is refused. The interface reports that as
“The search service is unavailable.”

### On your computer only

```bash
SEARCHER_PAGES_URL=https://joshuahickscorp.github.io/searcher/ \
SEARCHER_PAGES_ORIGIN=https://joshuahickscorp.github.io \
./scripts/serve_shared.sh --port 8770
```

Binds `127.0.0.1`. A friend cannot reach that. Open the printed
**API origin** in your own browser. Default port is 8765 if it is
free; `--port` or `SEARCHER_API_PORT` overrides it.

### Same network (`--lan`)

```bash
SEARCHER_PAGES_URL=https://joshuahickscorp.github.io/searcher/ \
SEARCHER_PAGES_ORIGIN=https://joshuahickscorp.github.io \
./scripts/serve_shared.sh --lan --port 8771
```

Binds the machine's LAN address. Send the printed **API origin**
(`http://<lan-ip>:<port>/`). That origin also serves the interface,
so the friend's browser stays on HTTP-to-HTTP.

Do **not** send the printed Pages `?api=http://...` URL for LAN or
loopback. That is an HTTPS page calling an HTTP address. The
browser refuses it. It looks like the service is down.

Anyone on the same network who has the URL can use the
unauthenticated API.

### Public tunnel (`--tunnel`)

Requires `cloudflared` already installed. The script will not
install it, create an account, or sign anyone up. If `cloudflared`
is missing it prints that and exits.

```text
./scripts/serve_shared.sh --tunnel
```

The tunnel is HTTPS. Two URLs then work:

1. The printed public tunnel URL itself (same origin, serves `web/`).
2. `https://joshuahickscorp.github.io/searcher/?api=<https-tunnel>`
   only if `SEARCHER_PAGES_ORIGIN=https://joshuahickscorp.github.io`
   was set so CORS allows the Pages origin.

Anyone with that URL can run searches against your machine. When
you stop the process, tell them it is down.

This file documents the tunnel. It does not open one.

## CORS allowlist

`SEARCHER_CORS_ORIGINS` is a comma-separated allowlist. `*` is
ignored. Credentials are never paired with a wildcard.

The process default is localhost on ports 8765, 8080, and 8000. It
does **not** include `https://joshuahickscorp.github.io`.

`scripts/serve_shared.sh` builds a list for the chosen mode and
appends `SEARCHER_PAGES_ORIGIN` when that variable is set.
`scripts/run_api.sh` does not add the Pages origin. That is why
local troubleshooting uses the local interface, not Pages.

| Frontend origin | API | Works? |
|---|---|---|
| `http://127.0.0.1:<port>/` served by the API | same origin | Yes |
| `http://<lan-ip>:<port>/` served by the API | same origin | Yes, same network |
| Pages `?api=https://<tunnel>` | HTTPS, Pages origin allowlisted | Yes |
| Pages `?api=http://127.0.0.1:<port>` | HTTPS page, HTTP private API | No — mixed content / private-network rules |
| Pages `?api=http://<lan-ip>:<port>` | HTTPS page, HTTP LAN API | No — mixed content |
| Pages, Pages origin not allowlisted | any | No — CORS; looks unavailable |

## Model weights

A fresh clone contains no model weight files (`*.pt`, `*.onnx`, and
the other extensions listed in `.gitignore`). Searcher never
downloads them.

There is no published Searcher weight file to fetch. If you already
have a local file you can point at it with
`SEARCHER_EMBEDDING_WEIGHTS`, or place it at
`data/models/embedding.pt` or `data/models/clip.pt`. The backbone is
DINOv2 ViT-S/14, prepared once by `scripts/prepare_embedding_weights.py`.
A search never downloads. Availability is a successful probe call, not
file existence. A dummy or unreadable file reports unavailable. The
service runs without weights and answers using classical descriptors.
Nothing is promoted to Real through a missing-weight fallback.

The optional VisionMCP donor is a local library pin, not a weight
download. See [architecture/DONOR_SETUP.md](architecture/DONOR_SETUP.md).

## Where data is written

Default: `data/` under the clone. Override with
`SEARCHER_DATA_ROOT`.

That directory holds `searcher.sqlite` (and WAL/SHM files) and
`data/objects/`. Uploads, derived images, and campaign-private
artifacts live there.

```bash
uv run searcher store stat
```

prints object counts for the current data root.

`uv run searcher capabilities` is the light visual-lane probe. It
does not start the HTTP server.

## How to delete it

One search: `DELETE /v1/searches/{search_id}` returns 204.
Subsequent reads of that search are 404. Receipts and shared
content-addressed objects remain. See [PRIVACY.md](../PRIVACY.md).

Everything the process wrote:

```bash
# Stop the process first.
rm -rf data
```

If you set `SEARCHER_DATA_ROOT`, remove that directory instead.

Browser drafts on the static page are separate. Clear site data in
the browser if you want those gone too.

## How to stop

Ctrl-C the script. That is a full stop. There is no background
daemon. `--lan` is one process. `--tunnel` stops the API and the
tunnel together.

Tell anyone you shared with that it is down.
`GET /v1/health` failing is the machine check.

## More

- [architecture/SERVING.md](architecture/SERVING.md) — health contract
- [LIMITATIONS.md](../LIMITATIONS.md)
- [CLAIMS.md](../CLAIMS.md)
- [PRIVACY.md](../PRIVACY.md)
- [web/README.md](../web/README.md) — the static interface
