# Operator clean-clone receipt

Public clone of https://github.com/joshuahickscorp/searcher
at `a66414e`. Scratch tree discarded after this receipt.

## Timings

```text
clone                1.42s
uv_sync              0.59s
capabilities         1.06s
api_up               0.92s
search             124.60s
clone_to_search    310.44s
test_all           320.74s
```

`clone_to_search` is wall time from `git clone` to a terminal
search, including operator checks (CORS, capabilities, port
conflict). Machine path clone → sync → API up → terminal search
is about 128 seconds. The search itself was 115–125 seconds.

Default `./scripts/run_api.sh` failed in 0s with
`[Errno 48] … 127.0.0.1:8765: address already in use`.
`SEARCHER_API_PORT=8766 ./scripts/run_api.sh` bound and answered
health in 0.92s.

## First search

`POST /v1/searches` with `fixtures/images/trainer_a.png`,
text `Dior Homme General Army Trainer 07`, tag `footwear`.

- `search_id` `1d79dd19-26f8-492a-95ec-b837e7a62cba`
- terminal `PARTIAL` after 114.76s
- reason: useful coverage remains incomplete; some sources blocked
- public results: Real 0, Possibly Real 0
- hidden: 8
- coverage: wikimedia / heroine `SEARCHED_NO_MATCH`; kind /
  the_realreal / byronesque `SEARCHED_MATCHES_FOUND`; komehyo
  `SOURCE_UNAVAILABLE`; ebay `AUTH_REQUIRED`
- `GET /v1/capabilities`: `discovery.available = true`,
  `routing.available = true`, donor `importable: false`
- no weight files in the clone
- `DELETE` → 204; later `GET` → 404
- `rm -rf data` after stop removed the data root

## `./scripts/test_all.sh`

Exit 0.

```text
250 passed, 3 skipped, 1 deselected in 224.48s
1 passed, 253 deselected in 93.48s
```

## Pages

- `GET https://joshuahickscorp.github.io/searcher/` → 200, 10826 bytes
- `GET https://joshuahickscorp.github.io/searcher/v1/health` → 404
- published `app.js` contains the unavailable banner

## CORS (API on 8766, default allowlist)

| Origin | `Access-Control-Allow-Origin` |
|---|---|
| `https://joshuahickscorp.github.io` | missing |
| `http://127.0.0.1:8766` | missing |
| `http://127.0.0.1:8765` | echo |
| `http://127.0.0.1:8080` | echo |

With `SEARCHER_PAGES_ORIGIN=https://joshuahickscorp.github.io`
on `serve_shared.sh --port 8770`, Pages origin is echoed and
`http://evil.example` is not.

## Weights

`find` on the clone: no `*.pt` / `*.onnx` / `*.safetensors`
outside the venv. No `data/models`.

`find_local_weights()` is `None`. After writing a dummy
`data/models/embedding.pt`, the gateway reports the file and
`embed_png` still returns `None`.
