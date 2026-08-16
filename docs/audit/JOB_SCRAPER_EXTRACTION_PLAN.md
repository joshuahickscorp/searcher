# Job Scraper extraction plan

**Donor located** at `<home>/Desktop/jobscraper` on 2026-08-16 and
frozen to `<home>/.searcher-donors/jobscraper-frozen-20260816/`
(manifest digest `3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2`).
This file is the implementable follow-on to
`docs/audit/JOB_SCRAPER_CAPABILITY_HARVEST.md`. A later discovery/acquisition
task should follow this plan **without re-reading the donor**.

This task does **not** vendor files or write Searcher product code. It names
exactly what lands where.

---

## 0. Integration rung (Bible §6.9)

There is no git SHA, so rung 1 (`REUSE_AS_PACKAGE` pinned to SHA) is closed.

Rung 2 (adapter around the local package) is rejected: importing `jobscraper`
pulls `curl_cffi`, `tf-playwright-stealth`, `user_agents.pick_ua`, and
`browser.browser_session`. Bible §6.10 forbids that surface in-process.

**Chosen rung:** Searcher-owned adapter (Bible §26.7) wrapping **minimal ports**
of isolated honest primitives, reimplementing everything the donor lacks or
taints. Provenance is the content digest above, cited in each ported file
header. Do **not** copy a frozen subtree into `src/`.

```text
src/searcher/integrations/job_scraper/   adapter + provenance only
src/searcher/sources/                    acquisition engine (ports + reimplements)
src/searcher/normalization/              listing mapping (reimplement)
```

---

## 1. Target tree

Create these modules in the implementing task. Names are normative.

```text
src/searcher/integrations/job_scraper/
    __init__.py
    adapter.py              # JobScraperAdapter protocol + Null/InProcess impl
    provenance.py           # FROZEN_PATH, MANIFEST_DIGEST, FREEZE_DATE, EXCLUSIONS

src/searcher/sources/
    __init__.py
    frontier.py             # REIMPLEMENT — donor has no frontier
    work_key.py             # PORT idea from db.upsert_job PK
    http.py                 # PORT DomainLimiter + honest httpx client
    robots.py               # PORT RobotsCache / RobotsBlocked
    retry.py                # PORT get_json retry/Retry-After classification
    circuit.py              # PORT company_state breaker, keyed by source_id
    cache.py                # REIMPLEMENT body+etag cache (donor etag-only is a defect)
    fetch_log.py            # PORT db.log_fetch shape
    escalate.py             # REIMPLEMENT CACHE → HTTP → LIGHT_RENDER → BROWSER
    events.py               # REIMPLEMENT progress events
    cancel.py               # REIMPLEMENT cooperative cancel
    adapters/
        __init__.py         # PORT resolve_fetcher registry shape
        protocol.py         # Searcher SourceAdapter (Bible §14.3)
        generic.py          # REIMPLEMENT JSON-LD / OG / selector fallback
    liveness.py             # PORT classify skeleton; new listing patterns

src/searcher/normalization/
    html.py                 # PORT strip_html, parse_iso_date
    url.py                  # REIMPLEMENT canonicalization (donor missing)
    listing.py              # REIMPLEMENT ListingCandidate mapping
```

Do **not** create `src/searcher/integrations/job_scraper/vendor/` in the first
extraction. If a later task disagrees, it still must not vendor the REJECT
set in the harvest §3.

---

## 2. Searcher-owned adapter surface (Bible §26.7 + §14.3)

`src/searcher/integrations/job_scraper/adapter.py` is the only module other
Searcher packages import. It must **not** import donor `scraper.*`.

```python
class JobScraperAdapter(Protocol):
    async def start_source_run(self, plan: SourcePlan) -> SourceRunRef: ...
    async def next_discovery_batch(self, run: SourceRunRef) -> DiscoveryBatch: ...
    async def fetch_candidates(self, urls: list[str]) -> list[FetchResult]: ...
    async def resume(self, run: SourceRunRef) -> SourceRunState: ...
    async def cancel(self, run: SourceRunRef) -> None: ...
```

Implementation notes for the later task:

| Method | What to do | What not to do |
|---|---|---|
| `start_source_run` | Persist a `SourceRunRef` (run id, source, query, budget, cursor=None) in Searcher's store. Enqueue the first work keys on the frontier. | Do not iterate `companies.yaml`. Do not call `runner.run_fetch`. |
| `next_discovery_batch` | Pop a bounded batch from the frontier (priority in Bible §15.1). Return URLs/queries + cursors. | Do not probe Greenhouse/Lever slugs. Those are job-domain discovery. |
| `fetch_candidates` | Escalate per `escalate.py`. Return `FetchResult` with status class `{ok, empty, blocked, robots, timeout, transient, terminal}`. | Do not call `HttpClient.get_html(..., impersonate=...)`. Do not rotate UA/proxies. |
| `resume` | Rebuild run from frontier + fetch_log + cached bodies + normalized candidates (Bible §15.6). Skip work keys in a terminal-success state. | Do not "just run update again". The donor's resume is a full refetch — that is a defect, not a contract. |
| `cancel` | Set a run-scoped cancel event; abort in-flight tasks; close HTTP/browser; persist `cancelled`. | Do not rely on Ctrl-C in `web.run`. |

The adapter **must not** expose `NormalizedJob`, `fit_score`, intern gates, or
ATS names to the rest of Searcher (Bible §26.7 last sentence).

Map donor-inspired persist onto Searcher types:

| Donor | Searcher |
|---|---|
| `(company, source_job_id)` | `(source_id, work_key)` where `work_key` is the canonical URL or listing id |
| `jobs` row | `ListingCandidate` + `FetchAttempt` |
| `company_state` | per-`source_id` circuit / health (Bible §14.6, §15.8) |
| `http_cache` etag | real cache: etag **and** body digest + policy TTL |
| `fetch_log` | `FetchAttempt` ledger |
| `is_active` / deactivate_missing | listing liveness, not CRM `queued/applied/oa` |

---

## 3. What to port, symbol by symbol

Copy by **retyping** into Searcher modules (minimal port), cite the digest in
a one-line header. Do not copy stealth or job-domain branches "and delete
later".

### 3.1 Port now

| Donor `path:symbol` | Lands at | Keep | Rewrite / drop |
|---|---|---|---|
| `http_client.DomainLimiter` | `sources/http.py` | per-host lock + `base_delay` + jittered sleep | drop ATS-vs-custom host sets; configure from source manifest `rate_policy` |
| `http_client.RobotsCache` / `RobotsBlocked` | `sources/robots.py` | `urllib.robotparser`, cache per origin, fail-open vs fail-closed is a **policy knob** (donor fail-opens — Searcher should default fail-closed on robots fetch error unless policy says otherwise) | do not use rotating UA as the robots product token; use a single honest UA |
| `http_client.HttpClient.get_json` retry block | `sources/retry.py` | 4-attempt ceiling, `wait_exponential_jitter(1, 30)`, retry transport + 429/5xx, `Retry-After` cap 60s | apply to **all** methods including POST and HTML; classify 403/challenge as terminal **block**, not retry |
| `db.is_breaker_open` / `record_company_failure` / `record_company_success` | `sources/circuit.py` | threshold 3, open for hours, success resets | key by `source_id`; emit source-health `blocked` (Bible §15.8); never open a stealth bypass |
| `db.upsert_job` + `transaction` | `sources/work_key.py` + Searcher store | PK upsert, `first_seen` preserved, `last_seen` refreshed, BEGIN/ROLLBACK | work key is canonical URL/listing id; no `fit_score` columns |
| `db.log_fetch` / `trim_fetch_log` | `sources/fetch_log.py` | append-only attempts with status/latency/error | add run_id, work_key, classification |
| `fetchers.resolve_fetcher` / `FETCHER_REGISTRY` | `sources/adapters/__init__.py` | name → callable registry | register Searcher source adapters, not ATS |
| `fetchers.base.strip_html` | `normalization/html.py` | tag strip + entity unescape + whitespace crush | fine as-is |
| `fetchers.base.parse_iso_date` | `normalization/html.py` | format list + `fromisoformat` fallback | keep; add listing date formats later |
| `liveness.classify` (404/410, `MIN_CONTENT_CHARS`) | `sources/liveness.py` | dead on gone; conservative on unknown; no deactivate on fetch fail | drop `APPLY_PATTERNS`, intern "position has been filled", `/careers` heuristics unless re-validated for marketplaces |
| `liveness.sweep` loop shape | `sources/liveness.py` | bounded `jobs_needing_liveness` analogue: oldest unchecked first, limit N | key off listing ids; honor robots; honest HTTP only |

### 3.2 Reimplement (donor contract is missing or wrong)

| Capability | Why not port | Contract the later task must implement |
|---|---|---|
| Frontier | no table, no priority, no cursor | Bible §15.1–15.2, §15.6. Durable work items with state `{pending, inflight, done, blocked, cancelled}`. Resume skips `done`/`blocked`. |
| Fetch escalation | no ladder; 304 returns empty body | Bible §15.3: CACHE_HIT → DIRECT_HTTP → LIGHT_RENDER → FULL_BROWSER. Escalate only when required fields are missing and policy allows. |
| Response cache | etag-only; `content_hash` unused; 304 → `[]` | Store body bytes + etag + last-modified + content digest + fetched_at + policy. 304 must replay the body. |
| URL canonicalization | absent | Bible §6.5 / §17.1: scheme/host, strip tracking params, listing-id extract, source-specific rules inside adapters. |
| Generic extraction | absent (no JSON-LD/OG/selectors) | Bible §14.4. |
| Progress events | prints/logs only | Bible §6.8: source start, query dispatch, candidates found, pages fetched, images, dedupe, block, complete. |
| Cancel | Ctrl-C on dashboard | Bible §10.5: run-scoped cancel, every await checks it, terminal persist. |
| Honest browser | only stealth persistent profiles exist | Bible §15.4: one browser, no personal profile, no private cookies, timeouts, close/reap, leak test. **Defer** until a source is admitted for render. |
| Block vs empty | empty list = success | Bible §15.8 / §3.8. |

### 3.3 Reject — do not copy, vendor, or "adapt"

See harvest §3 for the full §6.10 list. Implementing-task checklist:

- [ ] no `user_agents.py`
- [ ] no `browser.py`
- [ ] no `tf-playwright-stealth` / `playwright_stealth`
- [ ] no `curl_cffi`
- [ ] no `ProxyPool` / `JOBSCRAPER_PROXIES_FILE`
- [ ] no `--disable-blink-features=AutomationControlled`
- [ ] no `data/profiles`
- [ ] no `human_pause`
- [ ] no weighted UA pool
- [ ] no `filters.py` / `role_keywords.py` / `fit_score` / intern/citizenship/grad-year gates
- [ ] no ATS fetchers (`greenhouse.py` … `workday.py`, `stripe.py`, `shopify.py`) as Searcher sources
- [ ] no `NormalizedJob` in Searcher public types
- [ ] no `cli.py` / `web.py` / `export.py` / `stats.py`
- [ ] no `pyrate-limiter` (unused in donor; Searcher rate limits live in `DomainLimiter` + manifest)

A polite static User-Agent identifying Searcher is written in
`sources/http.py` as a constant, not a pool.

---

## 4. Dependencies: take / replace / refuse

| Donor dep | Decision | Justification |
|---|---|---|
| `httpx[http2]` | **take** (pin a current 0.27–0.28 or Searcher's already-chosen HTTP client) | Honest HTTP/2, timeouts, redirects. Used by `get_json`. |
| `tenacity` | **replaceable** | 15 lines in `sources/retry.py` is enough. Take it only if Searcher already wants the library. |
| `pydantic` | **defer to Searcher models** | Donor uses it for `CompanyConfig`/`NormalizedJob`. Searcher §9 types may already be dataclasses. Do not import donor models. |
| `PyYAML` | **only if** source manifests stay YAML (Bible §14.2 is YAML-shaped). JSON is fine. | |
| `structlog` | **replace** | Searcher logging. Do not add a log stack for this port. |
| `playwright` | **defer** | Honest render lane only, later, with a leak test. Never with stealth. |
| `tf-playwright-stealth` | **refuse** | §6.10. |
| `curl_cffi` | **refuse** | JA3 impersonation. |
| `pyrate-limiter` | **refuse** | Declared, never imported. Per-host limiter is `DomainLimiter`. |
| `respx` | **refuse as runtime**; optional for Searcher HTTP tests | Unused in donor tests. |

Do not add donor deps to Searcher `pyproject.toml` in a later task "just in
case". Each add needs a call site in the ports above.

---

## 5. Persistence schema the later task should create

Do **not** reuse `db.SCHEMA` (job CRM columns: `applied`, `oa`, `fit_score`,
`year_eligibility`, …). New tables, Searcher-owned:

```text
source_run(run_id, source_id, plan_digest, state, cursor, budget_used, started_at, updated_at)
frontier(run_id, work_key, url, priority, state, attempts, cursor, last_error_class, updated_at)
  PRIMARY KEY (run_id, work_key)
fetch_attempt(id, run_id, work_key, started_at, status, classification, latency_ms, error, content_digest)
response_cache(url_canonical, etag, last_modified, content_digest, body_ref, fetched_at, policy)
source_health(source_id, consecutive_failures, breaker_open_until, last_success_at, last_block_class)
```

Provenance of the **ideas**: `db.SCHEMA` `jobs` PK, `http_cache`,
`company_state`, `fetch_log` in the frozen snapshot. The CRM tables are
discarded.

Interrupt/resume contract the later task must test (the donor failed this):

1. Persist run + two work keys; complete key A; crash before key B commits.
2. Resume: A is not refetched; B is fetched once; no duplicate candidates.
3. Mid-transaction crash of B rolls back B and leaves A intact.
4. 304 on a cached URL replays the body and does not look like "0 results".

---

## 6. Job-domain rewrites (do not "tune" — replace)

These encode the internship applicant. If a later task needs a filter, it
writes a **listing-quality** filter against Searcher types.

| Donor behaviour | Searcher replacement |
|---|---|
| `passes_intern_title` | required-field check: title + canonical URL + at least one image or price, per source manifest |
| `passes_location` / Ottawa-Toronto bumps | user tags / campaign constraints, never a hard-coded city list |
| `fit_score` / `RANK_EXPR` | Bible §21 ranking (match evidence, authenticity completeness, liveness) |
| `passes_citizenship_gate` / sponsorship scores | drop |
| `detect_oa_vendor` | drop |
| `tag_cycle` / `infer_year_eligibility` | drop |
| `purge_non_interns` | drop |
| ATS `normalize` field maps | per-marketplace adapters mapping to `ListingCandidate` (§16.1): title, price, currency, size, availability, images, seller, timestamps |
| `liveness` apply-CTA regex | marketplace sold/removed language, HTTP gone, canonical redirect off-listing |

---

## 7. Implementation order for the later task

1. `provenance.py` with the digest (no donor import).
2. `normalization/html.py` + tests ported from greenhouse fixture *helpers*
   (strip/parse only — do not port `filter_jobs`).
3. `sources/http.py` + `robots.py` + `retry.py` + `circuit.py` + tests with a
   local `http.server` or `respx`. Honest UA constant. No network to ATS.
4. `sources/work_key.py` + `fetch_log.py` + `cache.py` (body-inclusive) + the
   four interrupt tests in §5.
5. `sources/frontier.py` + `escalate.py` + `events.py` + `cancel.py`.
6. `sources/adapters/protocol.py` + `generic.py`.
7. `integrations/job_scraper/adapter.py` wiring the above to §26.7.
8. Compatibility tests in Searcher (not donor): adapter start/resume/cancel
   against fixtures. **Still no live third-party hits** until a source is
   admitted under Bible §14.5.

Do not start with Playwright. Do not start with ATS modules. Do not start
with the dashboard.

---

## 8. Provenance blurb to paste into ported files

```text
# Ported idea from Job Scraper frozen snapshot
# path: <home>/.searcher-donors/jobscraper-frozen-20260816/
# manifest digest: 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2
# freeze: 2026-08-16
# donor symbol: scraper.<module>:<symbol>
# license: MIT as declared in donor pyproject.toml (no LICENSE file)
# §6.10: stealth / UA rotation / TLS impersonation / proxy rotation not ported
```

---

## 9. Out of scope for the implementing task (owned elsewhere)

- Searcher package scaffolding / `pyproject.toml` (concurrent task)
- `docs/architecture/**`, VisionMCP / MTP harvests, `REUSE_DECISIONS.md`,
  `DEPENDENCY_AND_LICENSE_AUDIT.md` (concurrent task — this plan is the Job
  Scraper correction those docs should cite)
- Vendoring any donor file
- Contacting Greenhouse, Lever, or any live ATS
