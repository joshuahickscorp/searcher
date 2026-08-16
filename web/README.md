# Searcher web interface

Static HTML, CSS, and ES modules. No build step, no dependencies.

## Local

Serve the files and the development API together:

```text
python3 web/dev/stub_api.py
```

Open http://127.0.0.1:8765/

Or split the two so you can stop the API without losing the page:

```text
python3 -m http.server 8080 --directory web
python3 web/dev/stub_api.py
```

Open http://127.0.0.1:8080/?api=http://127.0.0.1:8765

`web/dev/` is not part of the GitHub Pages site.

## Configuration

`config.js` exports `API_BASE`. Override with `?api=`.
`?dev=1` turns on numeric intervals when the API supplies them.

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
