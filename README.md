# Searcher

Evidence-ranked search for a specific physical item, from photographs
and optional text.

You run the engine on your own computer. The public page at
[joshuahickscorp.github.io/searcher](https://joshuahickscorp.github.io/searcher/)
is only the interface. There is **no hosted API** and **no
authentication**. Anyone who can reach the process can create, read,
cancel, and delete searches.

Searcher is **not** a professional authenticator. A placement in Real
is an evidence ranking under the current policy version, not a
certificate of genuineness. A finished search can honestly return
nothing. Read [LIMITATIONS.md](LIMITATIONS.md) and
[CLAIMS.md](CLAIMS.md) before repeating anything about what it can do.

Status: pre-alpha. Version `0.1.0`.

## Is this for you?

Yes if you want to run a local search campaign against admitted public
sources and inspect why a candidate was kept or hidden.

No if you want a website that just works when you open it, a hosted
backend, accounts, or a professional authentication service. The
published page without your process running only says that the search
service is unavailable.

## This alpha does not

- authenticate callers;
- host a backend for you;
- stay reachable when your computer sleeps or the process stops;
- guarantee a result — empty Real and Possibly Real lists are allowed.

How to run it, share it, and delete the data:
[docs/OPERATING.md](docs/OPERATING.md).

## The two tabs

| Tab | What it means | What it is not |
|---|---|---|
| **Real** | High confidence under the available images, the active bucket policy (`matching-1` by default), a calibrated authenticity interval, and a live verified listing. | Not a professional authentication. Not a purchase recommendation. |
| **Possibly Real** | A plausible item match with incomplete, conflicting, or uncalibrated evidence. Uncertain candidates are preserved here. | Not a counterfeit shop. Hard mismatches and strong replica/scam vetoes are hidden, not shown as “possibly real.” |

There is no public Fake tab. Hidden candidates are not published as
accusations. See [SEARCHER_BUCKET_POLICY.md](SEARCHER_BUCKET_POLICY.md)
and [SEARCHER_AUTHENTICITY_POLICY.md](SEARCHER_AUTHENTICITY_POLICY.md).

## Run it

Requires [uv](https://docs.astral.sh/uv/). Python 3.13 is selected from
`.python-version`; you do not need it as your default interpreter.

```bash
git clone https://github.com/joshuahickscorp/searcher.git
cd searcher
uv sync
./scripts/first_run.sh
```

That one command reports which lanes are live, states whether the
learned visual backbone is present, starts the API and the interface,
runs a first search, and prints what to do next.

Open the URL it prints (http://127.0.0.1:8765/ when the default port
is free).

To see the lane report without starting anything:

```bash
./scripts/first_run.sh --check-only
```

If that port is already taken the process exits with `address already
in use`. Pick another port:

```bash
SEARCHER_API_PORT=8766 ./scripts/first_run.sh
```

Then open http://127.0.0.1:8766/

The server-only command (no self-check, no first search) is
`./scripts/run_api.sh`. Same port rule: `SEARCHER_API_PORT=8766
./scripts/run_api.sh`.

Use this local copy of the interface. Do **not** open the published
HTTPS page and point it at `http://127.0.0.1` — the browser refuses
that combination and the page looks as if the service is down. Details
are in [docs/OPERATING.md](docs/OPERATING.md).

A first live search can take a couple of minutes. Empty public lists
are an allowed honest outcome, not a finding that the item does not
exist.

## Sharing

**WARNING: This alpha has no authentication.** Whoever can reach the
printed URL can create searches, read results, and cancel or delete
campaigns.

`./scripts/serve_shared.sh` is how you let someone else reach the
process. It checks the port, CORS, and that the printed URL actually
answers. It refuses rather than printing a URL that cannot work.
`--lan` and `--tunnel` are opt-in.

```bash
./scripts/serve_shared.sh --help
```

The published page only works against an **HTTPS** API origin, and
only when that origin's CORS allowlist includes
`https://joshuahickscorp.github.io`. For local and LAN use, send the
API origin itself — that origin also serves the interface.

Full steps, CORS, data, weights, and how to stop:
[docs/OPERATING.md](docs/OPERATING.md).

## Visual donor and model weights

A fresh clone has no model weight files. Searcher never downloads
them. The service runs without them and answers with classical descriptors.
Nothing is promoted to Real through a missing-weight fallback. `./scripts/first_run.sh --check-only` states whether the
learned backbone is present and prints the single command that
installs it.

There is no published weight file to fetch. See
[docs/OPERATING.md](docs/OPERATING.md#model-weights).

The optional VisionMCP donor is a local library pin, not a weight
download. Without it, images still decode with Pillow and nothing is
promoted to Real through a degraded path. See
[docs/architecture/DONOR_SETUP.md](docs/architecture/DONOR_SETUP.md).

## What the tree implements

- Upload validation, EXIF quarantine, reference analysis, hypothesis
  portfolio, and query compilation.
- A campaign state machine with checkpoints, cancellation, crash
  resume, and hash-chained receipts.
- Source adapters for the admitted set in
  [SOURCE_POLICY.md](SOURCE_POLICY.md). International and
  `review_required` adapters ship **disabled**.
- Matching and authenticity that use classical local descriptors
  (Pillow BRIEF-like, OpenCV ORB when present) plus DINOv2 ViT-S/14
  when a local TorchScript file at `$SEARCHER_DATA_ROOT/models/embedding.pt`
  passes a real probe. A search never downloads weights. VisionMCP at
  the pinned SHA has no learned feature backbone, no part matcher, and
  no logo detector.
- An HTTP API (FastAPI, SQLite WAL, SSE) and a dependency-free static
  UI in `web/`. `scripts/run_api.sh` turns live listing discovery on.
  `GET /v1/capabilities` reports `discovery.available` and
  `routing.available` from the running process.

The public benchmark receipt is
`artifacts/searcher-public-benchmark.receipt.json` (`uv run python -m
benchmark --all`): recall@1 0.771, recall@5 1.0, MRR 0.867 over 35
queries, false Real 0, on the stated splits. Do not quote a number
that is not in that receipt.

Standing authority:
[docs/SEARCHER_FULL_IMPLEMENTATION_BIBLE.md](docs/SEARCHER_FULL_IMPLEMENTATION_BIBLE.md).

## More

- [docs/OPERATING.md](docs/OPERATING.md) — run, share, CORS, data, stop
- [LIMITATIONS.md](LIMITATIONS.md) — what Searcher does not claim
- [CLAIMS.md](CLAIMS.md) — the only sentences currently entitled
- [PRIVACY.md](PRIVACY.md) — uploads, deletion, no training, no telemetry
- [SECURITY.md](SECURITY.md) — threat model and what is implemented
- [ARCHITECTURE.md](ARCHITECTURE.md) — system graph and module map
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — licenses and donors
- [LICENSE](LICENSE) — Apache-2.0, Copyright 2026 Joshua Hicks
