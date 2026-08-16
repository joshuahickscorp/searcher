# Job Scraper — Capability Harvest

Inspection date (UTC): 2026-08-16T04:48:46Z  
**Status: FOUND on this host, but not an authoritative frozen donor.**

This finding **changes the supervising engineer's "Job Scraper was not
located" result.** It does **not** change Searcher's integration posture
to wrap or vendor the tree. The tree has no git SHA, mixes Bible §6.10
rejected mechanisms into the same HTTP/browser modules as the useful
primitives, and is a personal internship-application product — not a
clothing-search acquisition engine.

Adoption for Searcher's discovery/acquisition stack remains
**`REIMPLEMENT_FROM_CONTRACT`** against Bible §6 and §15, informed by
what this tree actually contains.

---

## 1. Presence evidence

### 1.1 What the brief expected

The supervising engineer reported: no directory under `$HOME`, no
`gh repo list` match for `joshuahickscorp`, no GitHub search hit; only
stale Claude memory at
`~/.claude/projects/-Users-<user>-Downloads-jobscraper/memory`.

### 1.2 What this audit observed

| Probe | Result |
| --- | --- |
| `<home>/Downloads/jobscraper` | **ABSENT** |
| `<home>/Desktop/jobscraper` | **EXISTS** — full Python package |
| `Desktop/jobscraper/.git` | **ABSENT** — not a git repository |
| Claude project memory | EXISTS; contents are CV style notes and a Hawking AI-tool scrub, not scrape-engine docs |
| Bounded `*scraper*` find (maxdepth 4, Library pruned) | only Desktop tree + Claude memory dir |
| Network / `gh` | **not run** (contract forbids network) |

README inside the Desktop tree still documents:

```text
cd <home>/Downloads/jobscraper
```

**Inferred:** the tree was moved from Downloads to Desktop without
updating docs and without taking a git snapshot.

### 1.3 Tree shape (observed)

```text
<home>/Desktop/jobscraper
  pyproject.toml          name=jobscraper 0.1.0, license text MIT, no LICENSE file
  README.md               "Fintech Internship Job Scraper"
  RUNBOOK.md
  companies.yaml
  scraper/                package (21 modules + fetchers/)
  tests/                  10 test_*.py, 232 def test_ (counted, not run)
  data/jobs.db            live SQLite + wal/shm
  data/profiles/          persistent Playwright profiles
  cv/                     personal CVs
  .venv/                  local env
  jobscraper.egg-info/    editable install metadata
```

Do not mutate this tree. It holds personal CVs, a live jobs database,
and browser profiles.

---

## 2. Git truth

There is none. No remotes, no SHA, no tags, no worktrees. The package
cannot be pinned. `VENDOR_FROZEN_SNAPSHOT` and `REUSE_AS_PACKAGE` are
unavailable as honest adoption decisions.

`pyproject.toml` claims MIT. No `LICENSE` file is present. That is not
a shippable provenance record.

---

## 3. What the product is (observed vs useful)

**Observed purpose** (README, models, filters): pull fintech internship
postings from official ATS JSON APIs (Greenhouse, Lever, Ashby,
Workable, SmartRecruiters, Workday) plus stealth Playwright scrapers
for custom career portals; score them for a specific applicant; track
applications in SQLite; serve a local dashboard.

**Useful to Searcher** (concepts, not code): cheap-first HTTP,
robots.txt, per-host delay, exponential backoff, circuit breaker, ETag
cache, discover-then-fetch, upsert/dedupe, liveness classification,
honest error types (`RobotsBlocked`, `CircuitOpen`, `FetchError`).

**Hostile to Searcher** (Bible §6.10): Chrome TLS/JA3 impersonation
(`curl_cffi`, `impersonate="chrome124"`), proxy rotation
(`JOBSCRAPER_PROXIES_FILE`), Playwright stealth
(`tf-playwright-stealth`), persistent per-company browser profiles,
`--disable-blink-features=AutomationControlled`, UA rotation to look
like a person.

---

## 4. Per-component harvest

Fields follow Bible §4.7. SHA is `none` for every row. License is
"claimed MIT in pyproject; no LICENSE file."

### 4.1 `scraper.http_client.HttpClient`

| Field | Record |
| --- | --- |
| donor | Job Scraper (Desktop tree) |
| path / symbol | `scraper/http_client.py:HttpClient` |
| purpose | Async HTTP with per-domain limiter, robots cache, ETag/Last-Modified, retries, optional proxy, TLS impersonation on HTML |
| input | URL, optional company key, headers |
| output | `(body, status)` or `FetchError` / `RobotsBlocked` / `CircuitOpen` |
| dependencies | httpx, curl_cffi, tenacity, sqlite cache tables |
| tests | `tests/test_lifecycle.py` and others **reported, not run** |
| runtime evidence | README claims "zero rate-limit responses across 100s of requests" — **reported, not verified** |
| authority ceiling | personal operational tool; no receipt |
| limitations | stealth and honest HTTP live in one class |
| security | proxy file, TLS impersonation, UA spoofing |
| performance | 1 conn/domain; ATS delay 1.0s; custom delay 4.0s |
| **adoption** | **REJECT** the class as a whole. Reimplement the honest subset (limiter, robots, backoff, ETag, circuit breaker) from contract. |

Related symbols: `DomainLimiter`, `ProxyPool` (**REJECT**),
`RobotsCache` (reimplement), `get_json` (honest ATS path), `get_html`
(impersonate — **REJECT**).

### 4.2 `scraper.browser.browser_session` / `new_stealth_page`

| Field | Record |
| --- | --- |
| path / symbol | `scraper/browser.py:browser_session` |
| purpose | Persistent Chromium context per company + stealth patches |
| **adoption** | **REJECT** (§6.10: conceal origin, steal/replay profiles, evade controls) |

Searcher browser capture, if any, wraps VisionMCP's governed
`perception.browser` / `browser_slot`, not this factory.

### 4.3 `scraper.discover` + `scraper.fetchers.*`

| Field | Record |
| --- | --- |
| path / symbol | `scraper/discover.py:probe_one`, `scraper/fetchers/{greenhouse,lever,ashby,workable,smartrecruiters,workday,custom/*}` |
| purpose | ATS slug probe + source-specific JSON normalize; Stripe/Shopify stealth HTML |
| **adoption** | **REJECT** as Searcher adapters (wrong domain). The *pattern* (source adapter + normalize into a owned contract) is **REIMPLEMENT_FROM_CONTRACT**. |

### 4.4 `scraper.runner._fetch_one`

| Field | Record |
| --- | --- |
| path / symbol | `scraper/runner.py:_fetch_one` |
| purpose | Per-company fetch + filter + upsert + deactivate-missing; maps `CircuitOpen` / `RobotsBlocked` / `FetchError` to stats |
| **adoption** | **REIMPLEMENT_FROM_CONTRACT** (discover/fetch/parse separation + honest status) |

### 4.5 `scraper.db`

| Field | Record |
| --- | --- |
| path / symbol | `scraper/db.py:upsert_job`, `deactivate_missing`, `is_breaker_open`, `record_company_failure`, `get_cache_meta`, `log_fetch` |
| purpose | SQLite upsert on `(company, source_job_id)`, circuit breaker, HTTP cache meta, fetch log |
| tests | `tests/test_db.py` 12 functions (counted) |
| **adoption** | **REIMPLEMENT_FROM_CONTRACT**. Schema is job-specific. Pattern (durable frontier + attempt log + breaker) is required by §6.1 / §6.4. |

### 4.6 `scraper.liveness.classify`

| Field | Record |
| --- | --- |
| path / symbol | `scraper/liveness.py:classify` |
| purpose | HTTP + regex bank → `active` / `expired` / `uncertain`; no Playwright unless already required |
| tests | `tests/test_liveness.py` 8 functions (counted) |
| **adoption** | **REIMPLEMENT_FROM_CONTRACT** for listing sold/404/malware pages. Do not copy the job-posting regex bank. |

### 4.7 `scraper.filters` / `fit_score` / `role_keywords`

| Field | Record |
| --- | --- |
| path / symbol | `scraper/filters.py:filter_jobs`, `fit_score` |
| purpose | Internship / geography / grad-year ranking for one applicant |
| tests | `tests/test_filters.py` 115 functions (counted) — largest suite, all domain-specific |
| **adoption** | **REJECT**. Bible §6.7: do not reuse job-specific ranking as authenticity logic. |

### 4.8 `scraper.web` dashboard / `cli`

| Field | Record |
| --- | --- |
| path / symbol | `scraper/web.py:run`, `scraper/cli.py:main` |
| purpose | Local `127.0.0.1:8765` dashboard and `scraper update|top|apply|…` |
| **adoption** | **REJECT** (wrong product). |

### 4.9 `scraper.models.NormalizedJob`

| Field | Record |
| --- | --- |
| path / symbol | `scraper/models.py:NormalizedJob` |
| purpose | Pydantic job record |
| **adoption** | **REJECT** as a type. Searcher's `ListingCandidate` (Bible §9.9) is the authority. |

---

## 5. Contract Searcher must reimplement (Bible §6 + §15)

Searcher owns `src/searcher/…` acquisition. The following is the
contract, not a copy of Job Scraper.

### 5.1 Durable frontier (§6.1, §15.1, §15.6)

- Persist URL / work-key frontier across process death.
- Priority queue + cursor + attempt history + source progress + depth.
- Deduplicated work keys (canonical URL + listing id).
- Resume from last checkpoint; idempotent retries.

### 5.2 Discovery / fetch / parse / normalize / verify (§6.2)

Separate stages. A discovery URL is not a listing. A fetched page is
not a candidate. A parsed candidate is not a match.

### 5.3 Cheap-first escalation (§6.3, §15.3)

1. cache  
2. structured public endpoint / feed if admitted  
3. direct HTTP  
4. lightweight HTML parse  
5. public page render  
6. full browser only when necessary and permitted  

Default browser process count: 1. Hard cap: 3.

### 5.4 Retry / backoff / circuit breaking / block detection (§6.4, §15.8)

- Exponential backoff + jitter; honour `Retry-After`.
- Per-host ceilings; retry only transient classes.
- Circuit breaker per host/source; do not hammer a refusing source.
- Classify: timeout, DNS, TLS, HTTP 429/5xx, robots deny, captcha/block
  page, hard 404, sold, parse failure, policy refuse.
- Never treat a block as "source contained no result" (Bible §3.8).

### 5.5 URL canonicalization and dedupe (§6.5, §17)

Tracking-parameter strip, redirect resolution, listing-id extraction,
source-specific canonical forms. Dedupe by URL, then text, then image.

### 5.6 Extraction adapters (§6.6, §14)

JSON-LD, Open Graph, source selectors, generic fallback, images, price,
availability, size, currency, title, description, seller, timestamps.
Searcher contracts are the authority; source schemas stay inside
adapters.

### 5.7 Filtering (§6.7)

Dead pages, duplicates, malformed records, source-domain rules, required
fields, stale results, language, spam. **Not** internship fit scores.

### 5.8 Progress, cancellation, rate limits, cleanup (§6.8, §15.4–15.5)

Events: source start, query dispatch, candidates found, pages fetched,
images downloaded, dedupe, comparison, promotion, source block,
completion. Cancellation must stop in-flight fetches and reap browser
processes.

### 5.9 Storage

Searcher-owned SQLite/files under the campaign. Content-address listing
images via the VisionMCP artifact adapter when imaging is available.

### 5.10 Hard boundary — Bible §6.10 REJECT list

Do **not** implement, port, or "temporarily" enable:

- defeating authentication
- evading access controls
- solving or bypassing CAPTCHAs
- rotating identities to circumvent enforcement
- stealing or replaying browser profiles
- accessing private networks
- ignoring robots / source terms
- concealing origin (TLS impersonation, stealth patches, fake UA as
  evasion)
- uncontrolled request volume
- exposing credentials to models

The Desktop tree implements several of these (`curl_cffi` impersonate,
`tf-playwright-stealth`, `ProxyPool`, persistent `data/profiles/`).
They are evidence of what **not** to take.

---

## 6. Mapping Bible §4.5 checklist → this tree

| §4.5 item | In Desktop tree? | Searcher action |
| --- | --- | --- |
| crawl frontier | implicit (companies.yaml + last_seen) — not a general URL frontier | reimplement |
| persistent queue | SQLite jobs table | reimplement |
| checkpoint / resume | process-level only; no campaign checkpoint | reimplement |
| URL canonicalization | weak (ATS ids) | reimplement |
| source adapters | ATS fetchers | reimplement for marketplaces |
| browser adapters | stealth Playwright | **REJECT** implementation; wrap VisionMCP if needed |
| direct HTTP | `HttpClient.get_json` | reimplement honest subset |
| retry / backoff | tenacity + Retry-After | reimplement |
| block detection | partial (429, robots) | reimplement + captcha/block page class |
| status classification | `FetchError` / `RobotsBlocked` / `CircuitOpen` / liveness | reimplement, expand |
| parsing / extraction | ATS JSON + HTML stealth | reimplement |
| selector fallback | custom Stripe/Shopify only | reimplement generic |
| structured-data extraction | not general JSON-LD | reimplement |
| dedupe | `(company, source_job_id)` | reimplement URL/text/image |
| normalization | `NormalizedJob` | Searcher `ListingCandidate` |
| filtering | intern/geo ranking | **REJECT** ranking; reimplement quality filters |
| progress events | structlog + dashboard | reimplement SSE events |
| cancellation | asyncio task cancel (not audited as complete) | reimplement |
| rate limiting | `DomainLimiter` | reimplement |
| process cleanup | Playwright context manager | reimplement + VisionMCP `browser_slot` |
| storage / schema | SQLite jobs | reimplement |
| tests | 232 functions claimed network-free | do not run here; do not import |
| secrets | optional `JOBSCRAPER_PROXIES_FILE` | do not copy |
| §6.10 mechanisms | present | **REJECT** |

Interruption/resume was **not** reproduced (out of scope; would mutate
or execute the tree).

---

## 7. Adoption summary

| Component | Decision |
| --- | --- |
| Tree as a package | **REIMPLEMENT_FROM_CONTRACT** (no SHA; wrong domain) |
| Honest HTTP patterns | **REIMPLEMENT_FROM_CONTRACT** (do not import `HttpClient`) |
| Stealth / impersonation / proxy / persistent profiles | **REJECT** |
| ATS fetchers, intern filters, dashboard, CV extras | **REJECT** |
| Liveness *idea* | **REIMPLEMENT_FROM_CONTRACT** for listings |
| Vendoring this tree | **REJECT** |
