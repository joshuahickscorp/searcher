# Searcher source policy

Bible §39 name. Draws from `SOURCE_POLICY.md`,
`docs/sources/SOURCE_FAMILY_ADMISSION.md`, and
`docs/sources/SOURCE_RESEARCH_2026-08-16.md` (fetches of 2026-08-16).
Technical accessibility is not permission.

Honest User-Agent:

```text
Searcher/0.1.0 (+https://github.com/searcher-project/searcher; research-discovery; contact=operators@searcher.invalid)
```

## How a live campaign chooses sources

`src/searcher/workers/api_campaign.py:uncredentialed_source_names`
walks `searcher.sources.broker.DEFAULT_ORDER` and keeps every adapter
that is admitted, enabled, and does not require an operator
credential. Commit `31e6004` replaced a hand-typed seven-name list
with that derivation. The commit message records the result as ten
sources. eBay and Etsy are dropped because they cannot answer without
a key.

Command that names the current plan (no network):

```text
uv run python -c "from searcher.workers.api_campaign import uncredentialed_source_names; print(uncredentialed_source_names())"
```

This session ran that command at SHA
`31e6004c76e1d845447e0993a5ce68948f311265` and received exactly
those ten, in broker order: `searx`, `wikimedia`, `marginalia`,
`the_realreal`, `rebag`, `komehyo`, `kind`, `byronesque`,
`heroine`, `archive_org`.

A refusal (robots, terms, 401/403/429/challenge) is recorded as the
matching `SourceOutcome` and is never collapsed into
`SEARCHED_NO_MATCH`.

Search creation accepts repeated `source_scopes` of `legitimate`
and/or `replica`. Absent defaults to `legitimate`. A candidate from a
replica-family source, or a self-declared replica, is published only
in the Replica list.

## Admission table

The full per-source rights table is `SOURCE_POLICY.md`. Summary of
states that matter at this SHA:

**Admitted and enabled, no operator key (the live plan).**
SearxNG (own instance; public instances are not the production path),
Wikimedia, Marginalia, Internet Archive, The RealReal, Rebag,
Komehyo, KIND, Byronesque, Heroine.

**Admitted API-only; planned only if a key is present.**
eBay Browse API, Etsy Open API v3. Without a key they report
`AUTH_REQUIRED`. They do not scrape public HTML search pages.

**`review_required`, shipped disabled.**
Vinted, Mercari JP, Yahoo Auctions, Buyee, Bunjang, SSENSE,
Farfetch, StockX, GOAT, Poshmark, DuckDuckGo HTML, Depop.

**Cannot be admitted without defeating a challenge or ignoring robots.
Stay disabled.**

| Source | Why disabled | Evidence |
|---|---|---|
| Grailed | Listing pages return a Cloudflare challenge | `src/searcher/sources/adapters/pending.py` GRAILED; `docs/sources/SOURCE_REVERIFY_2026-08-16.md` |
| Vestiaire Collective | HTTP robots and listing fetches challenged | same, VESTIAIRE |
| Taobao | Item URLs typically `Disallow` | same, TAOBAO |
| Weidian | robots.txt redirected to a 404 page | same, WEIDIAN |
| Yupoo | no fetchable robots file | same, YUPOO |

Depop is also disabled (plain HTTP 403 / challenge). DHgate is out of
scope and must not be registered. Serper / SerpAPI are out of scope.

KIND is admitted for product and collection pages. `Disallow: /search`
is honoured. Destination verification of a KIND listing has been
observed to return a challenge; a blocked verification fetch is
recorded `UNCHECKED`, not as missing evidence against the listing
(`tests/unit/test_verification.py::test_a_blocked_fetch_is_unchecked_not_absent`).

## What is not established

- That every name in the ten-source plan actually produces coverage
  on a given live campaign. Commit `31e6004` records that Rebag is in
  the plan and still was not attempted on the run that provoked the
  change. A committed campaign receipt whose coverage lists Rebag as
  `SEARCHED_MATCHES_FOUND` is not in this tree.
- Openverse appears in `SOURCE_POLICY.md` as admitted and is not in
  `DEFAULT_ORDER` / `ADAPTER_REGISTRY`. It is not part of the live
  plan.
