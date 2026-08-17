# Searcher UX specification

Bible §39 name. The standing product spec is Bible §24. The
implementation is the static tree under `web/` (no build step, no
dependencies). Operator notes: `web/README.md`. Field contract:
`web/API_EXPECTATIONS.md`. Serving: `docs/architecture/SERVING.md`.

## Design principle

A focused utility, not a marketplace. Almost no explanation before
use.

## What the shipped page implements

Published at `https://joshuahickscorp.github.io/searcher/` from `web/`
by `.github/workflows/pages.yml`. That origin does not run the API.

Initial surface (`web/index.html`):

- image drop zone, 1–10 JPEG / PNG / WebP / GIF;
- text box;
- tags box;
- Search button, disabled until the form is valid;
- optional name field, prefixed into `text` as `Name: …`;
- optional source-scope preference (`?scopes=legitimate,replica`).

After Search:

- results stream over SSE;
- campaign status and human-readable stages remain visible;
- tabs: Real, Possibly Real, and Replica when replica-family
  sources were searched;
- each card carries image, title, source, price, availability, last
  checked, item-match and authenticity labels, evidence chips, Open
  listing (new tab), Compare, and Why this result;
- empty Real / empty all-candidates copy matches Bible §24.9 in
  substance;
- privacy and limitations pages at `#/privacy` and `#/limitations`.

Keyboard operation, visible focus, semantic labels, and a reduced-
motion path are present in `web/index.html` / `web/styles.css` /
`web/js/`. Mobile layout exists (`artifacts/ui/after-phone-390x844.png`
and the desktop counterparts).

Progress language follows Bible §24.4
(Understanding the item, Reading visible labels, …).

There is no authentication. Anyone who can reach the API can create,
read, cancel, and delete searches. The page stores only local drafts,
display preferences, and recent search identifiers.

## What is not on the first page

Bible §24.10 advanced controls (size, price maximum, region,
condition, search depth, include sold, retention) are not a first-
page form. Some of those can be inferred from tags. Retention stays
at the schema default `session`.

Crops and the hypothesis portfolio are not API fields, so they are
not shown (`artifacts/searcher-flagship-matched.receipt.json`
behaviours 2 and 5: not evaluable).

Numeric score intervals are hidden unless `?dev=1`.

## What is not established

- An independent accessibility audit (WCAG score, contrast
  measurement, screen-reader pass). Keyboard and contrast were
  exercised in `artifacts/ui/` captures; that is not a formal audit.
- That the published Pages page, pointed at a live tunnel, was
  used by a stranger in a search whose results are committed here.
  The path is documented (`docs/OPERATING.md`). A committed
  campaign receipt of that exact use is not in this tree.
- Seeded demonstration searches (`fixture-normal`, …) in
  `web/README.md` describe the development stub
  (`web/dev/stub_api.py`), not the operator API.
