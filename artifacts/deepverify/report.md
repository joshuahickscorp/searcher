# Deep-verify lane report

## What landed

1. A listing-page verification pass (`src/searcher/verification/`) runs after
   live-check and before publication. It re-opens the candidate URL, extracts
   JSON-LD Product, then microdata, RDFa, Open Graph, then the adapter parse.
   Each of price, availability, title, seller, images is recorded as
   `agrees` / `disagrees` / `absent` with `checked_at` and a reason.
   A disagreement is evidence. The candidate is still published.
2. A rendering fetcher (`Escalator.render`) behind admission → robots → rate
   limit → budget → one fetch. Playwright is an optional extra. Absent it,
   HTTP behaviour is unchanged. A challenge is `BLOCKED_BY_ACCESS` plus
   classification_note `BLOCKED_BY_CHALLENGE: <marker>`. No retry.

`SourceOutcome` stays at the Bible's 11 values. A 12th member would break
`test_enums_cover_bible_values` (`len(SourceOutcome) == 11`).

## Tests (new)

- robots-disallowed URL is refused by `render()`; browser is never called
- challenge page is one fetch, `BLOCKED_BY_CHALLENGE` note, no retry
- JSON-LD, microdata, RDFa, and the absent case
- price change → `disagrees`, candidate kept, change stated
- JS-only local page: empty over HTTP, parses under Playwright
- BrowserPool closes page/context when `goto` raises; no leftover Chromium

Each of those failed when the behaviour was deliberately broken, then restored.

## Timing (local fixture, robots already cached, 600 rpm)

See `artifacts/deepverify/timing.txt`.

- Warm HTTP median: 93.3 ms (host limiter ~100 ms)
- Warm render median: 46.5 ms
- Cold render (first Chromium page): 348.1 ms
- Added cost of a cold rendered fetch versus warm HTTP: about +255 ms
- Browser orphans after the run: none

## Pending sources (none newly permitted)

See `docs/sources/SOURCE_REVERIFY_2026-08-16.md` and
`artifacts/deepverify/source-reverify.json`.

All six stay `review_required` / disabled.

## Verification sample

`artifacts/deepverify/verification-sample.json` — permitted source `rebag`,
fields include agrees, a price `disagrees`, and seller `absent`. The
recorded price is unchanged; the change is in the explanation.

## Sparse-checkout blocker

`./scripts/test_all.sh` and several existing tests need paths that are not
materialized here: `scripts/test_all.sh`, `tests/support/`, `migrations/`.
`uv run ruff check .` and `uv run mypy src` are clean on this tree. New
tests and the related existing unit tests pass.
