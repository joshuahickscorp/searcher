# Searcher web interface

Static HTML, CSS, and ES modules. No build step, no dependencies.
Published at https://joshuahickscorp.github.io/searcher/ from `web/`
by `.github/workflows/pages.yml`. That origin does not run the API.

## Operator (the real engine)

The process that answers searches is started from the repository root:

```text
./scripts/run_api.sh
```

That serves this directory at the API origin (default
http://127.0.0.1:8765/), so `config.js` can keep `API_BASE = ""`.

Use that local copy for local work. Do not open the published HTTPS
page with `?api=http://127.0.0.1:…`. The browser refuses an HTTPS
page calling a private HTTP origin; the banner then says the search
service is unavailable.

Sharing, CORS, and the tunnel: [docs/OPERATING.md](../docs/OPERATING.md).

`web/dev/` is a stub for UI development. It is not the operator API
and is not part of the GitHub Pages site.

## Local stub (UI development only)

Serve the files and the development stub together:

```text
python3 web/dev/stub_api.py
```

Open http://127.0.0.1:8765/

Or split the two so you can stop the stub without losing the page:

```text
python3 -m http.server 8080 --directory web
python3 web/dev/stub_api.py
```

Open http://127.0.0.1:8080/?api=http://127.0.0.1:8765

## Configuration

`config.js` exports `API_BASE`. Override with `?api=`.
`?dev=1` turns on numeric intervals when the API supplies them.
`?scopes=legitimate,replica` carries the source-scope preference on a shared link.
The optional name field is prefixed into `text` (`Name: …`). There is no extra API field.

## Routes

```text
#/
#/search/{id}
#/search/{id}/result/{resultId}
#/privacy
#/limitations
```

Seeded demonstration searches: `fixture-normal`, `fixture-empty-real`,
`fixture-empty`, `fixture-cancelled`, `fixture-failed`, `fixture-blocked`,
`fixture-partial`, `fixture-xss`.

A new search picks a scripted scenario from the text or tags
(`empty-real`, `empty`, `xss`, `blocked`, `partial`, `cancel`, `error`).
