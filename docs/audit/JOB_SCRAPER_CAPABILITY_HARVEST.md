# Job Scraper capability harvest

**Correction notice.** A concurrent audit task was told Job Scraper did not
exist. That is false. The donor was located at
`<jobscraper-live-checkout>` on 2026-08-16 and frozen the same day.
This file is the Job Scraper harvest. It is the correction.

This document inspects the **frozen snapshot only**. The live checkout is
read-only comparison evidence. `data/`, `cv/`, `jobs.db`, and the contents of
`companies.yaml` are the user's private material and are not quoted here.

Evidence classes used below:

- **Observed:** executed in this harvest (tests, fixture run, interrupt script,
  hash verification).
- **Source:** cited `path:symbol` in the frozen snapshot.
- **Donor-reported:** README / RUNBOOK / module docstrings. Not treated as proof.
- **Inference:** stated as inference.

---

## 0. Freeze

| Field | Value |
|---|---|
| Live checkout (off limits except listing/hash compare) | `<jobscraper-live-checkout>` |
| Frozen snapshot (read-only) | `$SEARCHER_JOBSCRAPER_FROZEN_DIR/` |
| Manifest | `$SEARCHER_JOBSCRAPER_FROZEN_DIR.manifest.sha256` |
| Manifest digest (`shasum -a 256` of the manifest file) | `3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2` |
| File count | 45 |
| Git SHA | none — donor is not a git repository |
| Declared license | MIT in `pyproject.toml` (`license = { text = "MIT" }`). No `LICENSE` file in the snapshot. |
| Package | `jobscraper` 0.1.0, `requires-python = ">=3.11"` |

### 0.1 Manifest verification (observed)

```text
$ shasum -a 256 $SEARCHER_JOBSCRAPER_FROZEN_DIR.manifest.sha256
3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2  $SEARCHER_JOBSCRAPER_FROZEN_DIR.manifest.sha256

$ cd $SEARCHER_JOBSCRAPER_FROZEN_DIR && shasum -a 256 -c ...manifest.sha256
```

All 45 paths reported `OK`. Re-run after pytest produced the same 45 `OK` lines.
The snapshot directory is mode `dr-x------`; `touch README.md` returns
`Operation not permitted`.

### 0.2 Exclusions (why the snapshot is smaller than the live checkout)

The live checkout additionally contains `.venv/`, `.pytest_cache/`,
`jobscraper.egg-info/`, `.DS_Store`, `.claude/`, `data/`, `cv/`, and `jobs.db`.
Those were excluded from the freeze because they are a local environment, cache,
or the user's private job/CV data. This harvest does not read them.

All 45 snapshot files still byte-match the live checkout (SHA-256 compare
against the manifest). The live listing (excluding `data/`, `cv/`, `.venv/`)
was identical before and after this work:
`5824f8e28da9190c2677a13e7dbbe6e3d517802e45a52b666070a0ac3600eb94`.

### 0.3 What the donor is

A personal Python CLI that discovers **fintech internship postings** through
official ATS JSON endpoints (Greenhouse, Lever, Ashby, Workable, SmartRecruiters,
Workday) plus two stealth Playwright HTML scrapers (Stripe, Shopify). It stores
filter-passing rows in SQLite, scores them for one applicant, and drives a
loopback dashboard.

It is **not** a general URL crawler. It has no durable URL frontier, no crawl
cursor, no fetch-escalation ladder, and no URL canonicalizer. Several README
claims (token-bucket via `pyrate-limiter`, 114 tests, working stealth import)
are stale or false relative to the code. See §6 answers.

---

## 1. Module map

Every path is under
`$SEARCHER_JOBSCRAPER_FROZEN_DIR/`.

### 1.1 `scraper/__init__.py`

| | |
|---|---|
| Purpose | Package marker. |
| Public symbols | `__version__ = "0.1.0"` |
| I/O | none |
| Dependencies | none |
| Errors / concurrency / persistence | none |
| Tests | none |
| Limitations | Version is not imported by CLI. |

### 1.2 `scraper/models.py`

| | |
|---|---|
| Purpose | Pydantic contracts for company config and a normalized job row. |
| Public symbols | `AtsName`, `Country`, `CycleTag`, `RoleCategory`, `YearEligibility`, `utcnow`, `CompanyConfig`, `NormalizedJob` |
| Input | dicts / kwargs. `CompanyConfig` allows extra fields (`extra="allow"`). `NormalizedJob` ignores extras. |
| Output | typed models. Required on `NormalizedJob`: `company`, `source_job_id`, `title`, `application_url`, `ats_source`. |
| Dependencies | `pydantic` |
| Errors | Pydantic validation errors. |
| Concurrency | none |
| Persistence | none directly; `db.upsert_job` serializes `NormalizedJob`. |
| Tests | constructed in almost every test module. |
| Limitations | Entirely job-domain. `fit_score`, `cycle_tag`, `year_eligibility`, `oa_vendor` are applicant-ranking fields, not listing identity. |

### 1.3 `scraper/config.py`

| | |
|---|---|
| Purpose | Load/save/filter the company registry YAML. |
| Public symbols | `DEFAULT_PATH`, `load_companies`, `save_companies`, `find_company`, `filter_companies` |
| Input | path to YAML list of company dicts. |
| Output | `list[CompanyConfig]`. Missing file → `[]`. |
| Dependencies | `yaml`, `models.CompanyConfig` |
| Errors | YAML / validation errors propagate. |
| Persistence | `save_companies` overwrites the YAML path. Used by `runner.run_discover` once at the end of the loop. |
| Tests | none dedicated. `cli` / `stats` call it. |
| Limitations | **Do not read `companies.yaml` contents.** File role only: operator-maintained ATS registry (`name`, `ats`, `slug`, `tier`, `workday_host`/`site`, `requires_browser`, researched `algo_gate` / `underclassman`). Discover persists resolved `ats`/`slug` back into this file. Mid-loop crash loses in-memory resolutions (source: `runner.run_discover`). |

### 1.4 `scraper/db.py`

| | |
|---|---|
| Purpose | SQLite schema, job upsert, application-pipeline state machine, HTTP cache metadata, per-company circuit breaker, fetch log. |
| Public symbols | `SCHEMA`, `DEFAULT_DB`, `connect`, `transaction`, `upsert_job`, `deactivate_missing`, `find_jobs_by_token`, `mark_applied`, `unmark_applied`, `list_applied`, `STATUSES`, `ACTIVE_STATUSES`, `STALE_DAYS`, `set_status`, `set_referral`, `set_saved`, `clear_cache`, `pipeline_counts`, `stale_in_state`, `auto_ghost`, `update_liveness`, `jobs_needing_liveness`, `get_cache_meta`, `save_cache_meta`, `get_company_state`, `is_breaker_open`, `record_company_success`, `record_company_failure`, `log_fetch`, `trim_fetch_log` |
| Input | `sqlite3.Connection` + domain objects / keys. |
| Output | bools, row lists, counts. `upsert_job` → `True` iff newly inserted. |
| Dependencies | stdlib `sqlite3`/`json`, `models.NormalizedJob`/`utcnow`. |
| Errors | `set_status` raises `ValueError` on unknown status. `transaction` rolls back on exception. |
| Concurrency | `connect` uses `check_same_thread=False`, `isolation_level=None` (autocommit), `PRAGMA journal_mode=WAL`, 30s busy timeout. Dashboard serializes writes with `web.run`'s `scraper_lock`. Scraper workers share one connection from `cli.main` — **inferred risk** under concurrent `upsert` from `run_fetch` workers. |
| Persistence | tables `jobs` PK `(company, source_job_id)`, `status_history`, `http_cache` PK `url` (etag / last_modified / unused `content_hash`), `company_state`, `fetch_log`. |
| Tests | `tests/test_db.py` (12), `tests/test_lifecycle.py` (15). **Observed** pass. |
| Limitations | This is a **job CRM**, not a crawl frontier. `http_cache` stores validators only — no body. `content_hash` is never written by `HttpClient.get_json`. No work-item table, no cursor, no run id. `last_success_at` is written and never read by `runner.run_fetch`. |

### 1.5 `scraper/http_client.py`

| | |
|---|---|
| Purpose | Async HTTP with per-host delay, retries, robots (HTML only), ETag conditional GET, optional proxy pool, TLS impersonation on HTML. |
| Public symbols | `ATS_BASE_DELAY`, `CUSTOM_BASE_DELAY`, `ATS_DOMAINS`, `FetchError`, `RobotsBlocked`, `CircuitOpen`, `DomainLimiter`, `ProxyPool`, `RobotsCache`, `HttpClient` |
| Input | URL + optional company name (for breaker / fetch_log). |
| Output | `get_json` → `(parsed \| None, status)`. `None` means 304 **or** non-200 after raise path. `get_html` → `(text \| None, status)`. |
| Dependencies | `httpx`, `tenacity`, `curl_cffi` (HTML path), `user_agents.pick_ua` / header builders, `db` (breaker, cache meta, fetch_log). **`pyrate-limiter` is declared in `pyproject.toml` and never imported.** |
| Errors | `CircuitOpen` if `db.is_breaker_open`. `RobotsBlocked` if robots deny (HTML only). `FetchError` on JSON decode / curl failure. Transport and 429/5xx retried in `get_json` only. |
| Concurrency | one `DomainLimiter` lock per host (serializes that host). Process-wide `HttpClient`. `run_fetch` caps company workers with `asyncio.Semaphore(workers=4)`. |
| Persistence | `db.log_fetch` on every attempt; `db.save_cache_meta` on HTTP 200 JSON. Written **outside** the jobs transaction. |
| Tests | none for the client itself. `respx` is a declared test extra and unused. |
| Limitations | See §6.3, §6.4, §6.10. `get_html` impersonates Chrome JA3 (`impersonate="chrome124"`). `ProxyPool.pick` randomly rotates proxies. `pick_ua` rotates identity every request. ATS JSON is **not** robots-checked. Workable/Workday POST go through `client._httpx` and skip `get_json`'s retry/cache/breaker. |

### 1.6 `scraper/user_agents.py` — **§6.10 REJECT**

| | |
|---|---|
| Purpose | Weighted browser User-Agent rotation plus Chrome Client-Hints / `Sec-Fetch-*` spoofing so requests look like a human browser. |
| Public symbols | `UA_POOL`, `pick_ua`, `base_headers`, `json_headers` |
| Input | optional UA / referer. |
| Output | header dict. `pick_ua` uses `random.choices` weighted by a Statcounter-like share. |
| Dependencies | stdlib `random`. |
| Tests | none. |
| Limitations | Docstring: "Realistic UA pool, weighted by approximate Statcounter share". This is identity rotation and origin concealment. A single static honest UA would be fine; this module is not. |

### 1.7 `scraper/browser.py` — **§6.10 REJECT**

| | |
|---|---|
| Purpose | Stealth Playwright session factory. |
| Public symbols | `PROFILE_ROOT`, `VIEWPORTS`, `LOCALES`, `TIMEZONES`, `BLOCKED_RESOURCES`, `browser_session`, `new_stealth_page`, `human_pause` |
| Input | `company_slug`, `headed`. |
| Output | `BrowserContext` (async context manager). |
| Dependencies | `playwright.async_api`, `tf_playwright_stealth.Stealth` (optional import), `user_agents.pick_ua`. |
| Errors | stealth apply is swallowed (`stealth_apply_failed`). |
| Concurrency | one persistent Chromium context per call. |
| Persistence | `data/profiles/{company_slug}` via `launch_persistent_context` — cookies/localStorage replayed across runs. |
| Tests | none. Playwright Chromium was **not** installed in the throwaway env; this module is untested at runtime. |
| Limitations | Module docstring states the intent: stealth, persistent profiles, realistic viewport/locale/timezone, random pre-action delays. Launch args include `--disable-blink-features=AutomationControlled`. `human_pause` is a randomized sleep to look human. `finally: await context.close()` plus `async_playwright()` teardown **does** close the context on normal/exception paths. There is no PID tracking, no leak test, and a SIGKILL leaves Chromium children unreaped (**inference** from process model; not SIGKILL-tested). |

Installed `tf-playwright-stealth==1.2.0` exports `playwright_stealth.stealth_async`, not `tf_playwright_stealth.Stealth`. The donor import `from tf_playwright_stealth import Stealth` therefore fails, is caught, and stealth is a no-op at this pin. The **purpose** is still evasion. REJECT regardless of whether the import currently works.

### 1.8 `scraper/discover.py`

| | |
|---|---|
| Purpose | Guess ATS slug candidates from a company name and probe known board URLs until one returns a parseable payload. |
| Public symbols | `slug_candidates`, `PROBES`, `probe_one`, `discover_company` |
| Input | `CompanyConfig` + `HttpClient`. Skips if `ats=="custom"` and `requires_browser`, or if already resolved. |
| Output | same `CompanyConfig` mutated with `ats`/`slug`, or unchanged. |
| Dependencies | greenhouse/lever/ashby/workable/smartrecruiters `board_url`, `HttpClient.get_json`. **Workday is not probed.** |
| Errors | probe exceptions → `None` (treated as miss). |
| Concurrency | sequential slugs × ATS. Live network. |
| Persistence | none in this module; `runner.run_discover` writes YAML after the whole loop. |
| Tests | `tests/test_discover.py` — `slug_candidates` only (4 tests). No probe tests. |
| Limitations | This is **ATS endpoint discovery**, not a URL frontier. Each successful probe is a live GET (`use_cache=False`). Not run in this harvest (would hit live ATS). |

### 1.9 `scraper/runner.py`

| | |
|---|---|
| Purpose | Per-company fetch orchestration: resolve adapter → fetch → filter → upsert → deactivate missing → circuit success/fail. Discover loop. |
| Public symbols | `run_fetch`, `run_discover` (`_fetch_one` is module-private). |
| Input | sqlite connection, company list, `workers`. |
| Output | list of per-company stats dicts (`raw`, `role_pass`, `location_pass`, `new`, `deactivated`, `error`). |
| Dependencies | `db`, `config`, `discover`, `fetchers.resolve_fetcher`, `filters.filter_jobs`, `http_client`. |
| Errors | `CircuitOpen` / `RobotsBlocked` / `FetchError` recorded in `stats["error"]` and (except circuit) `record_company_failure`. Worker exceptions logged, not re-raised. |
| Concurrency | `random.shuffle(companies)` then `asyncio.as_completed` with semaphore. |
| Persistence | `db.transaction` wraps passing upserts + `deactivate_missing` + `record_company_success`. |
| Tests | none directly. Persist shape **observed** in `/tmp/.../interrupt_resume.py`. |
| Limitations | Always refetches every company. Empty `jobs_raw` (including JSON 304 → `[]`) counts as success and does **not** deactivate. `seen_ids` is the *raw* set so filter-drops do not deactivate previously stored rows. No cancel token. |

### 1.10 `scraper/fetchers/__init__.py` and `fetchers/base.py`

| | |
|---|---|
| Purpose | Adapter registry + tiny parse helpers. |
| Public symbols | `FetcherFn`, `FETCHER_REGISTRY`, `CUSTOM_REGISTRY`, `resolve_fetcher`; `parse_iso_date`, `strip_html` |
| Input | `CompanyConfig`. Custom key = `(slug or name).lower().replace(" ", "")`. |
| Output | `Callable[..., Awaitable[list[NormalizedJob]]] \| None`. |
| Dependencies | per-ATS modules. |
| Tests | greenhouse normalize covered; registry not unit-tested. |
| How to add a source (source) | write `fetchers/<ats>.py` with `fetch(client, company, slug, **kwargs) -> list[NormalizedJob]` (and optional `normalize` / `board_url`); register in `FETCHER_REGISTRY` or `CUSTOM_REGISTRY`. There is no generic HTML/JSON-LD fallback. Unregistered `ats` → `runner` error `no_fetcher_for_ats`. |

`fetchers/base.py` is **not** a class contract. There is no abstract `Fetcher` base. The contract is the call signature plus `NormalizedJob`.

### 1.11 Official ATS fetchers

All take `HttpClient`, company name, slug; return `list[NormalizedJob]`. None contact the network in this harvest.

| Module | Endpoint (source) | Parse | Tests | Limitations |
|---|---|---|---|---|
| `fetchers/greenhouse.py` | `GET boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | `jobs[]` → `id`, `title`, `absolute_url`, location/offices, departments, `updated_at` | `tests/test_normalize_greenhouse.py` **observed** | `body is None` → `[]` (304 hazard). |
| `fetchers/lever.py` | `GET api.lever.co/v0/postings/{slug}?mode=json` | list of postings; `createdAt` ms | none | same 304 → `[]`. |
| `fetchers/ashby.py` | `GET api.ashbyhq.com/posting-api/job-board/{slug}` | `jobs` or `data`; slug percent-encoded | none | same. |
| `fetchers/workable.py` | `POST apply.workable.com/api/v3/accounts/{slug}/jobs` paginated | `results`/`jobs` + `nextPage`/`token`; cap 20 pages | none | Uses `_httpx.post` + `pick_ua`. No tenacity, no cache, no breaker inside the fetcher. |
| `fetchers/smartrecruiters.py` | `GET api.smartrecruiters.com/v1/companies/{slug}/postings` | `content` + `totalFound`; page size 100, cap 20 | none | via `get_json`. |
| `fetchers/workday.py` | `POST https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` | `jobPostings`; `PAGE_SIZE = 20` (API 400 above 20) | none | Requires `workday_host`/`workday_site`. `_httpx.post`, `pick_ua`. Missing host/site → `[]`. Non-200 → silent stop. Donor-reported: many bank host/site guesses are wrong (RUNBOOK). |

### 1.12 Custom fetchers — **§6.10 REJECT (browser path)**

`fetchers/custom/stripe.py` and `fetchers/custom/shopify.py` launch
`browser_session` + `new_stealth_page`, `human_pause`, click/scroll, regex
listing links out of HTML. They ignore the `HttpClient` for the actual fetch.
Brittle selectors. No tests. Not executed (would hit live sites + need
Chromium).

### 1.13 `scraper/filters.py` — job-domain ranking (**do not carry into authenticity**)

| | |
|---|---|
| Purpose | Internship-only gates, location allow/drop, country/cycle/year inference, `fit_score` 0–100 for one applicant, `filter_jobs` funnel. |
| Public symbols | `has_intern_signal`, `passes_intern_title`, `passes_education_level`, `passes_citizenship_gate`, `passes_role`, `passes_location`, `infer_country`, `tag_cycle`, `infer_year_eligibility`, `fit_score`, `classify_role`, `enrich`, `recompute_active_enrichment` (alias `recompute_active_scores`), `purge_non_interns`, `filter_jobs` |
| Input | `list[NormalizedJob]` + company intel (`tier`, `algo_gate`, `underclassman`). |
| Output | `(passing, stats, drops)` where drops are `(job, stage, reason)` if requested. |
| Dependencies | `role_keywords.*`, `enrichment.parse_*`. |
| Tests | `tests/test_filters.py` 114, `tests/test_intern_title.py` 69, `tests/test_toronto_bump.py` 8. **Observed** pass. |
| Limitations | Hard-coded to one Canadian sophomore applicant (see `role_keywords.APPLICANT_GRAD_YEARS = {2029, 2030}`, Ottawa/Toronto bumps, US-citizenship drop). This is **exactly** Bible §6.7's forbidden reuse. |

Funnel stages in `filter_jobs` (source): title → education → citizenship → role → location → enrich → year (`junior`/`senior` hard-drop).

### 1.14 `scraper/role_keywords.py` — job-domain constants (**do not carry**)

Public constants: `POSITIVE_KEYWORDS`, `POSITIVE_PATTERNS_RAW`, `INTERN_SIGNAL_REGEX`, `INTERN_TITLE_REQUIRED_REGEX`, `PHD_REQUIRED_CONTEXT_REGEX`, `UNDERGRAD_SIGNAL_REGEX`, `TITLE_HARD_DROP_REGEX`, `HARD_NEGATIVE_PATTERNS`, `NEGATIVE_PATTERNS`, `NEGATIVE_MANAGER_PATTERN`, `UK_TERMS`, `EU_TERMS`, `LOCATION_ALLOW`, `PROVINCE_STATE_ABBR_REGEX`, `CITY_ABBR_REGEX`, `WEAK_ALLOW_TOKENS`, `AMBIGUOUS_REMOTE_TOKENS`, `LOCATION_DROP_HINTS`, `YEAR_PATTERNS`, `APPLICANT_GRAD_YEARS`, `YEAR_SCORE`, `CYCLE_SCORE`, `COUNTRY_SCORE`, `NO_SPONSORSHIP_PENALTY`, `SPONSORSHIP_BONUS`, `OTTAWA_AREA`, `TORONTO_AREA`, `OTTAWA_BUMP`, `TORONTO_BUMP`, `ROLE_FIT_SCORE`, `TIER_ACCESSIBILITY_SCORE`, `ALGO_GATE_SCORE`, `UNDERCLASSMAN_VERIFIED_BONUS`, `ROLE_CATEGORY_KEYWORDS`.

Comment at `YEAR_SCORE` states the profile: Canadian sophomore, accounting+math, CA-preferred. Entire file is applicant policy, not retrieval infrastructure.

### 1.15 `scraper/enrichment.py` — mostly job-domain

| | |
|---|---|
| Purpose | Pure text derivations from a JD body. |
| Public symbols | `parse_deadline`, `detect_oa_vendor`, `parse_requirements` |
| Input | JD string. |
| Output | `date \| None`; OA vendor name; dict of yoe/gpa/sponsorship/citizenship/comp/duration/education/majors/tech. |
| Tests | `tests/test_enrichment.py` 32. **Observed** pass. |
| Limitations | `detect_oa_vendor` (HackerRank/CodeSignal/…) is internship-pipeline specific. `parse_requirements` citizenship/GPA/YOE/majors are job-domain. `parse_deadline` (cue phrases + date forms) is the only piece that could inspire a generic "extract a dated deadline" helper — still rewrite against listing language, do not vendor. |

### 1.16 `scraper/liveness.py`

| | |
|---|---|
| Purpose | Classify whether a posting URL is still open. HTTP + regex, no Playwright. |
| Public symbols | `HARD_EXPIRED_PATTERNS`, `LISTING_PAGE_PATTERNS`, `EXPIRED_URL_PATTERNS`, `APPLY_PATTERNS`, `MIN_CONTENT_CHARS`, `LivenessResult`, `classify`, `sweep` |
| Input | `classify(http_status, final_url, body)` — pure. `sweep` walks `jobs_needing_liveness`. |
| Output | `state` in `{active, expired, uncertain}`, `deactivate` bool. |
| Dependencies | `HttpClient.get_html` (stealth HTML path), `db.update_liveness`, `db.auto_ghost`. |
| Errors | robots/network → skip row (status 0), do not deactivate. |
| Tests | `tests/test_liveness.py` 8, all on `classify`. **Observed** pass. `sweep` untested here (would network). |
| Limitations | `get_html` does not return the final redirected URL (comment in `_fetch_for_liveness`). Expired-body / apply-CTA patterns are job-board English. Generic reusable idea: 404/410 → dead; short body → uncertain/dead; do not deactivate on fetch failure. |

### 1.17 `scraper/export.py`

| | |
|---|---|
| Purpose | Query + CSV of ranked jobs. `RANK_EXPR` adds referral + approaching-deadline boosts at query time. |
| Public symbols | `CSV_FIELDS`, `RANK_EXPR`, `query_jobs`, `write_csv`, `export` |
| Tests | none dedicated; dashboard uses `RANK_EXPR`. |
| Limitations | Job CRM ranking. Not a Searcher export. |

### 1.18 `scraper/stats.py`

| | |
|---|---|
| Purpose | Print coverage / pipeline / open breakers. |
| Public symbols | `print_stats` |
| Tests | none. |
| Limitations | stdout report for the operator. |

### 1.19 `scraper/cli.py`

| | |
|---|---|
| Purpose | `scraper` console script (`pyproject` → `scraper.cli:main`). |
| Public symbols | `main`. Commands: `update`, `top`, `next`, `apply`, `pipeline`, `stats`, `serve`. Hidden: `status`, `list`, `doctor`, `sweep`, `fetch`, `discover`, `export`. |
| Input | argparse. Default DB `data/jobs.db`, companies file `companies.yaml`. |
| Output | process exit code. `update` = rescore + purge + discover + fetch + liveness sweep + blocking dashboard. |
| Dependencies | almost everything. |
| Concurrency | `asyncio.run` per subcommand. Dashboard blocks. |
| Tests | none for CLI parsing. |
| Limitations | Operator CRM. No Searcher campaign controller. `update --workers` default 4. No cooperative cancel of in-flight fetches. |

### 1.20 `scraper/web.py`

| | |
|---|---|
| Purpose | Loopback dashboard (`127.0.0.1:8765`). |
| Public symbols | `_row_to_card`, `_build_sections`, `_Handler`, `run` |
| Endpoints (source) | `GET /` HTML; `GET /api/sections` JSON; `POST /api/status`; `POST /api/save`. Module docstring also claims `GET /api/job/<pk>` — **that route is not implemented** in `do_GET`. |
| Concurrency | `ThreadingHTTPServer` + one shared sqlite connection + `threading.Lock`. |
| Persistence | status/save writes via `db.set_status` / `set_saved`. |
| Tests | `tests/test_web.py` 9, including a live loopback server. **Observed** pass. |
| Cleanup | `KeyboardInterrupt` → `server_close()` + `conn.close()`. Only cancel path in the donor. |
| Limitations | Job CRM UI. No auth (loopback only). Not a Searcher results drawer. |

### 1.21 Tests and fixture

| File | Tests | What they actually cover |
|---|---|---|
| `tests/test_filters.py` | 114 | role/location/country/cycle/year/fit_score |
| `tests/test_intern_title.py` | 69 | title/education/citizenship/grad-year gates + purge |
| `tests/test_enrichment.py` | 32 | deadline / OA / requirements parsers |
| `tests/test_lifecycle.py` | 15 | status machine, ghost, saved, cache clear, liveness column |
| `tests/test_db.py` | 12 | upsert, deactivate, breaker, applied, token, cache meta |
| `tests/test_web.py` | 9 | sections + HTTP handlers on loopback |
| `tests/test_toronto_bump.py` | 8 | GTA scoring |
| `tests/test_liveness.py` | 8 | `classify` only |
| `tests/test_discover.py` | 4 | `slug_candidates` only |
| `tests/test_normalize_greenhouse.py` | 3 | fixture normalize + filter funnel |
| **Total** | **274** | **0 skipped** |

`tests/fixtures/greenhouse_sample.json` — 4 synthetic Greenhouse jobs. This is the only recorded HTTP-shaped fixture.

**Not covered by tests:** `http_client.py`, `browser.py`, `user_agents.py`, `cli.py`, `runner.py`, `stats.py`, Workable/Workday/Lever/Ashby/SmartRecruiters fetchers, Stripe/Shopify, live robots, proxies, Playwright.

### 1.22 Root files (role only)

| Path | Role |
|---|---|
| `pyproject.toml` | package metadata, MIT declaration, dependencies, `scraper` script, pytest `asyncio_mode=auto` |
| `README.md` | operator quickstart; donor-reported "114 tests", "token-bucket", stealth stack |
| `RUNBOOK.md` | operator calendar and troubleshooting; contains user-specific apply advice — not reused |
| `companies.yaml` | company ATS registry. **Contents not read or quoted.** |
| `.gitignore` | ignores `data/`, venvs, caches |

---

## 2. Bible §6.1–§6.8, with evidence

### 2.1 §6.1 Persistent frontier

**Verdict: the donor does not have a durable URL/work frontier.** What it has is a job-row store plus side tables.

| Searcher need | Donor fact | Evidence |
|---|---|---|
| Durable URL frontier | Absent. Work unit is "a company in `companies.yaml`", not a URL. | `runner.run_fetch` iterates `list[CompanyConfig]`. No queue table in `db.SCHEMA`. |
| Priority queue | Absent for crawl. Ranking is `fit_score` / `RANK_EXPR` over **already stored jobs**. | `export.RANK_EXPR`, `filters.fit_score` |
| Cursor persistence | Absent. Workday/SmartRecruiters/Workable paginate **in memory** (`offset` / `token`) and throw the cursor away. | `workday.fetch` offset loop; `workable.fetch` `payload["token"]`; `smartrecruiters.fetch` offset |
| Restart recovery | Partial, accidental. Completed companies' **passing jobs** survive in SQLite. The next `update` refetches **all** companies. Mid-transaction crash rolls back that company. Mid-discover crash loses YAML updates. | Observed interrupt script; `runner.run_discover` calls `save_companies` after the loop; `db.transaction` BEGIN/COMMIT/ROLLBACK |
| Attempt history | `fetch_log` (url, status, latency, error) and `company_state.consecutive_failures`. Not a per-URL attempt ledger with work keys. | `db.log_fetch`, `db.record_company_failure` |
| Deduplicated work keys | Job identity `(company, source_job_id)` only. | `db.SCHEMA` `PRIMARY KEY (company, source_job_id)`; `db.upsert_job` |

`company_state.last_success_at` looks like a resume cursor. **It is not.** `runner.run_fetch` never reads it. Observed: after resume, both Acme and Brex show `last_success_at` and would still be fully refetched.

### 2.2 §6.2 Discovery / fetch / parse / normalize separation

**Verdict: adapter-shaped, stage-blended.**

```text
discover_company   →  mutate CompanyConfig.ats/slug   (ATS probe, not URL discovery)
fetcher.fetch      →  HTTP + parse + NormalizedJob    (three stages in one function)
filter_jobs/enrich →  job-domain gates + ranking
upsert_job         →  persist
liveness.sweep     →  later HTTP re-check
```

`FetcherFn` returns already-normalized `NormalizedJob` (`fetchers/__init__.py:FetcherFn`). There is no `RawListing` and no separate parse/normalize step as in Bible §14.3.

Discovery URLs are ATS board endpoints built from slugs (`greenhouse.board_url`), not a search SERP. A discovery hit is already "the full job list for this employer", not a candidate URL to fetch later.

Generic fallback: **none**. `resolve_fetcher` returns `None` → `no_fetcher_for_ats`.

### 2.3 §6.3 Cheap-first fetch escalation

**Verdict: not implemented.** There is no `CACHE_HIT → DIRECT_HTTP → LIGHT_RENDER → FULL_BROWSER` ladder.

What exists:

1. **Conditional GET metadata** (`http_cache.etag` / `last_modified`) on JSON only. On 304, `HttpClient.get_json` returns `(None, 304)`. `greenhouse.fetch` (and siblings) treat `None` as `[]`. **The cache does not store bodies.** A 304 is "no jobs this call", which `runner._fetch_one` treats as success and does not deactivate. Observed from source; 304 not HTTP-exercised (no network).
2. **Direct HTTP JSON** for official ATS (`get_json` / some POST).
3. **No light HTML parse lane** that is not also TLS-impersonated.
4. **Full stealth browser** only when the company's `ats=="custom"` resolves to Stripe or Shopify. Trigger is adapter identity, not a failed cheaper fetch.

Browser launch trigger (source): `resolve_fetcher` → `CUSTOM_REGISTRY` → `stripe.fetch` / `shopify.fetch` → `browser_session(...)`.

Do not launch a browser for every result — the donor already does not, but the path it *does* launch is a §6.10 stealth path and must not be reused.

### 2.4 §6.4 Retry and error classification

**Present (JSON path only):**

- Exponential backoff + jitter: `tenacity.AsyncRetrying(stop=stop_after_attempt(4), wait=wait_exponential_jitter(initial=1, max=30))` in `HttpClient.get_json`.
- Retryable: `httpx.TransportError` or HTTP 429/500/502/503/504.
- `Retry-After` honored, capped at 60s, then `raise_for_status` to trip tenacity.
- Per-host spacing: `DomainLimiter` (not a token bucket). `base_delay * random.uniform(0.7, 1.4)`. ATS hosts 1.0s, others 4.0s. One in-flight per host via `asyncio.Lock`.
- Circuit breaker: `db.record_company_failure(..., threshold=3)` opens for **6 hours**. `HttpClient.get_json`/`get_html` raise `CircuitOpen`.
- Robots: `RobotsCache` + `RobotsBlocked` on HTML. Missing/failed robots.txt parsed as allow-all.

**Absent or weak:**

- `get_html` has **no** retry loop.
- Workable/Workday POST bypass `get_json` (no tenacity, no ETag, no breaker inside the fetcher).
- No cause-specific retry beyond status/transport.
- No per-source "blocked vs empty" coverage flag. Empty list = success.
- No CAPTCHA classifier. No 403/challenge classification as terminal block.
- `pyrate-limiter` unused. README "token-bucket" is donor-reported and false.
- Block detection is "429/503 log + circuit after 3 company failures", not Bible §15.8 (stop identical retries, mark coverage blocked, continue alternatives).

### 2.5 §6.5 URL canonicalization and deduplication

**Canonicalization: absent.** `urllib.parse.urlparse` is used only for host extraction (limiters, robots) and dashboard routing. No tracking-parameter strip, no scheme/host normalize, no redirect-to-canonical store.

**Dedup: job id, not URL.** `PRIMARY KEY (company, source_job_id)`. IDs come from ATS (`greenhouse.normalize` uses `raw["id"]`; Workday falls back to `title|externalPath`). Two URLs for the same posting are not merged. `find_jobs_by_token` is an operator lookup, not a canonicalizer.

`liveness.EXPIRED_URL_PATTERNS` treats redirects to `/jobs`, `/careers`, `/search` as expired — the only URL-shape logic — and even that is undermined because `get_html` does not expose the final URL.

### 2.6 §6.6 Extraction adapters

**What exists:** one function per ATS that maps official JSON → `NormalizedJob`. Helpers: `strip_html`, `parse_iso_date`.

**What Searcher needs and the donor does not have:** JSON-LD, Open Graph, generic CSS selectors, image gallery extraction, price/currency/size/availability.

**New source recipe (source):** add module + registry entry. Optional `board_url` for discover probes.

**Contract to copy (shape only):**

```text
async def fetch(client, company: str, slug: str, **kwargs) -> list[NormalizedJob]
def normalize(company: str, raw: dict) -> NormalizedJob
```

Searcher must wrap this as Bible §14.3 / §26.7 (`discover` / `fetch` / `parse` / `normalize` / `live_check`) and emit `ListingCandidate`, not `NormalizedJob`.

### 2.7 §6.7 Filtering and quality controls

Reusable **ideas** (reimplement, do not vendor):

- reason-tagged drop stages (`filter_jobs` `drops`);
- dead-page classification (`liveness.classify` 404/410 / short body);
- do not deactivate on network/robots failure;
- required-field presence (`NormalizedJob` requires url/title/id);
- `deactivate_missing` as "source no longer lists this id".

**Job-domain ranking assumptions that must not enter product authenticity logic** (Bible §6.7):

| Symbol | Why it is applicant policy |
|---|---|
| `role_keywords.APPLICANT_GRAD_YEARS` | `{2029, 2030}` for one student |
| `YEAR_SCORE`, `CYCLE_SCORE`, `COUNTRY_SCORE`, `ROLE_FIT_SCORE` | convertibility for that student |
| `TIER_ACCESSIBILITY_SCORE`, `ALGO_GATE_SCORE`, `UNDERCLASSMAN_VERIFIED_BONUS` | interview-loop research, not listing quality |
| `OTTAWA_BUMP`, `TORONTO_BUMP`, `OTTAWA_AREA`, `TORONTO_AREA` | commute preference |
| `NO_SPONSORSHIP_PENALTY`, `SPONSORSHIP_BONUS` | visa policy for that applicant |
| `filters.fit_score`, `filters.passes_intern_title`, `passes_citizenship_gate`, `infer_year_eligibility` junior/senior drop | internship CRM gates |
| `export.RANK_EXPR` referral/deadline boosts | application-pipeline ranking |
| `enrichment.detect_oa_vendor` | HackerRank et al. |
| entire `POSITIVE_KEYWORDS` / intern regex banks | internship recall/precision |

Carrying any of these into authenticity or match scoring would violate §6.7 and §3 (observation ≠ inference; price/fit ≠ proof).

### 2.8 §6.8 Progress, cancellation, rate limits, process cleanup

| Need | Donor | Evidence |
|---|---|---|
| Progress events | `structlog` info/warning + `print` in CLI. No event bus, no campaign drawer events. | `runner.run_fetch` `log.info("company_fetch_done")`; `cli._cmd_update` prints |
| Cancellation | Dashboard `KeyboardInterrupt` only. Fetch tasks have no cancel. | `web.run` `except KeyboardInterrupt`; no `asyncio.Event` / `CancelledError` in `runner` |
| Rate limiting | `DomainLimiter` + worker semaphore. Not `pyrate-limiter`. | `http_client.DomainLimiter.acquire`; `runner.run_fetch` `Semaphore(workers)` |
| Browser lifecycle | `browser_session` closes context in `finally`. Persistent profiles on disk. Images/fonts/media aborted. | `browser.py` |
| Process leak | No PID file, no leak test. Normal path should close. SIGKILL / failed launch-before-try is untested. | no tests; inference |

---

## 3. §6.10 rejection list (complete)

Searcher must not reuse anything whose purpose is to look human, evade bot detection, rotate identity, or conceal origin. Named rejections:

| ID | Path:symbol | Why REJECT |
|---|---|---|
| R1 | `scraper/user_agents.py:UA_POOL` / `pick_ua` | Weighted UA rotation pool. Identity rotation to circumvent enforcement. |
| R2 | `scraper/user_agents.py:base_headers` Chrome `Sec-Ch-Ua*` / `Sec-Fetch-*` | Client-hint spoof so the client looks like Chrome navigation. Conceal origin. |
| R3 | `scraper/browser.py` (module) | Documented "Stealth Playwright session factory". |
| R4 | `scraper/browser.py:_apply_stealth` | Applies `tf_playwright_stealth.Stealth` to hide automation. |
| R5 | `scraper/browser.py:browser_session` `launch_persistent_context` + `PROFILE_ROOT` | Persists and **replays** cookies/localStorage per company (`data/profiles`). Browser-profile replay. |
| R6 | `scraper/browser.py` `--disable-blink-features=AutomationControlled` | Hides automation controlled flag. |
| R7 | `scraper/browser.py` random `VIEWPORTS` / `LOCALES` / `TIMEZONES` | Fingerprint diversification. |
| R8 | `scraper/browser.py:human_pause` | Randomized delay to mimic a human. |
| R9 | `scraper/browser.py:new_stealth_page` | Stealth page constructor. |
| R10 | dependency `tf-playwright-stealth` (`playwright_stealth` JS: `navigator.webdriver.js`, `webgl.vendor.js`, `chrome.runtime.js`, …) | Package summary: "spoofing browser features in order to reduce the chance of detection." |
| R11 | `scraper/http_client.py:HttpClient.get_html` `impersonate="chrome124"` / `curl_cffi` | TLS/JA3 fingerprint spoofing. Conceal origin. |
| R12 | `scraper/http_client.py:ProxyPool` | Random proxy rotation (`JOBSCRAPER_PROXIES_FILE`) to change apparent origin. |
| R13 | `scraper/fetchers/custom/stripe.py` / `shopify.py` | Only consumers of the stealth browser. |

**Not rejected (honest, keep the idea):**

- Honoring `robots.txt` (`RobotsCache` / `RobotsBlocked`).
- Per-host delay and retry ceilings.
- Circuit breaker that **stops** after repeated failure.
- A **single static** User-Agent that identifies Searcher.

**Also rejected for product reasons (not §6.10, but must not ship):** all of §2.7's job-domain ranking; ATS internship fetchers as Searcher sources; the dashboard/CLI CRM.

Do not port rejected symbols "for reference". Do not vendor those files.

---

## 4. Test baseline (observed)

Throwaway env: `/tmp/jobscraper-baseline-20260816/.venv` (CPython 3.11.15).
Nothing was installed into `<jobscraper-live-checkout>/.venv`.

```text
$ uv venv --python 3.11 /tmp/jobscraper-baseline-20260816/.venv
$ uv pip install --python .../python \
    "httpx[http2]>=0.27,<0.29" "curl_cffi>=0.7,<0.9" "pyrate-limiter>=3.6,<4.0" \
    "tenacity>=8.3,<10.0" "pydantic>=2.7,<3.0" "PyYAML>=6.0,<7.0" \
    "structlog>=24.1,<26.0" "playwright>=1.45,<2.0" "tf-playwright-stealth>=1.1,<2.0" \
    "pytest>=8.0,<9.0" "pytest-asyncio>=0.23,<1.0" "respx>=0.21,<1.0"
# Resolved 33 packages; installed 33. No install failure.

$ cd $SEARCHER_JOBSCRAPER_FROZEN_DIR
$ /tmp/jobscraper-baseline-20260816/.venv/bin/python -m pytest -q
........................................................................ [ 26%]
........................................................................ [ 52%]
........................................................................ [ 78%]
..........................................................               [100%]
274 passed, 1 warning in 4.01s
```

Warning: pytest could not write `.pytest_cache` into the read-only snapshot. Snapshot hashes unchanged after the run.

| | |
|---|---|
| Passed | 274 |
| Failed | 0 |
| Skipped | 0 |
| Playwright browsers | not installed; **not needed** by this suite |
| Network tests | none in suite |
| README claim | "114 tests, network-free" — **stale**. 114 is `test_filters.py` alone. |

`playwright install chromium` was not run. Stripe/Shopify/browser paths remain runtime-unverified (and are rejected).

---

## 5. Fixture runtime (observed, no network)

`tests/fixtures/greenhouse_sample.json` → `greenhouse.normalize` → `filter_jobs(with_reasons=True)`:

| id | title | result |
|---|---|---|
| 7000001 | Software Engineer Intern, Summer 2027 | **pass** — `country=CA`, `cycle=summer-2027`, `year=sophomore`, `role=engineering`, `fit=67` |
| 7000002 | Senior Backend Engineer | **drop** `title` / `no-intern-keyword` |
| 7000003 | Finance Intern, FP&A | **pass** — `country=US`, `cycle=current`, `year=any`, `role=finance`, `fit=44` |
| 7000004 | Product Manager Intern (London) | **drop** `title` / `title-drop:'Manager'` |

Stats: `raw=4`, `title_pass=2`, `edu_pass=2`, `role_pass=2`, `location_pass=2`.

This is the only recorded end-to-end extract→filter behaviour. Live ATS was not contacted.

Note: an older reading of the fixture test expected the London PM intern to die on **location**. Current `TITLE_HARD_DROP_REGEX` drops `Manager` first. The test still passes because it only asserts SWE+Finance present, Senior+London absent, `location_pass==2`.

---

## 6. Persistence verdict (observed, not assumed)

Bible §4.5: do not assume "persistent" means correct. Script:
`/tmp/jobscraper-baseline-20260816/interrupt_resume.py` against
`db.transaction` / `upsert_job` / `record_company_success` and the greenhouse
fixture. File-backed WAL DB at `/tmp/jobscraper-baseline-20260816/interrupt.db`.

| Step | Observation |
|---|---|
| Complete persist of Acme (filter-passing fixture jobs) | 2 rows (`7000001`, `7000003`). `company_state.Acme.last_success_at` set. |
| Brex persist raises `RuntimeError` after 1 upsert **inside** `db.transaction` | Brex row count **0**. Acme untouched. `company_state.Brex` is `None`. Rollback works. |
| Re-run Acme + Brex (the actual `update` resume behaviour) | Acme still 2 rows, **no duplicates**. `first_seen_at` preserved. `last_seen_at` refreshed. Brex inserts 2 new rows. |
| `last_success_at` | Written both times. **No skip.** Resume = full refetch. |
| Discover | Not file-exercised (`companies.yaml` is private). Source shows `save_companies` only after the entire loop → mid-discover interrupt loses all new slugs. |
| 304 / empty fetch | Source: empty `jobs_raw` → success, no deactivate. Does not lose prior rows. Does not apply cached bodies (there are none). |
| `fetch_log` / `http_cache` | Independent of the jobs transaction. Attempt crumbs, not a frontier. |

**Verdict.**

- Job **rows** are durable and idempotent under `(company, source_job_id)`.
- An interrupted **company persist** does not half-write (transaction).
- An interrupted **run** does **not** resume remaining work. It starts over and re-hits every source.
- There is no URL frontier, no work cursor, no exactly-once work key for "fetch this company this week".
- Searcher cannot adopt this as the campaign resume implementation. It can adopt the upsert-by-key and transactional persist **ideas**, reimplemented against Searcher's work items.

SIGKILL during an unflushed WAL frame was not tested. SQLite WAL usually recovers; that is inference, not observation.

---

## 7. Adoption summary

Decisions use only the §4.7 enum. Full field sets live in
`artifacts/audit/jobscraper-reuse-ledger.json`.

`REUSE_AS_PACKAGE` is unavailable: no git SHA, not a published pinned
distribution Searcher can depend on.

| Decision | Components |
|---|---|
| `PORT_MINIMAL_COMPONENT` | `DomainLimiter` (honest delay), `RobotsCache`/`RobotsBlocked`, tenacity-style retry/Retry-After, `company_state` circuit, `upsert` by work key + transactional persist, `fetch_log` shape, `FetcherFn` registry shape, `strip_html` / `parse_iso_date`, `liveness.classify` skeleton (404/410/short body only) |
| `REIMPLEMENT_FROM_CONTRACT` | URL frontier + cursors + resume, fetch-escalation ladder, URL canonicalization, generic page adapter (JSON-LD/OG/selectors), Searcher `ListingCandidate` normalize, campaign progress events, cooperative cancel, honest browser render (if ever needed), listing liveness language |
| `WRAP_WITH_ADAPTER` | Searcher-owned `JobScraperAdapter` (Bible §26.7) wrapping the **ported** primitives — not wrapping the donor process or its stealth stack |
| `VENDOR_FROZEN_SNAPSHOT` | not chosen for any runtime module. Stealth and job-domain code are entangled with useful bits. Prefer typed ports + provenance citation of this digest |
| `DEFER` | dashboard, CLI CRM, CSV export, stats printer, Playwright (honest) until a measured render need exists |
| `REJECT` | entire §3 list; `filters.py` / `role_keywords.py` / `fit_score` / intern gates; ATS/custom fetchers as Searcher sources; `NormalizedJob` as a product type; `curl_cffi`; `tf-playwright-stealth`; `ProxyPool`; `user_agents.py`; `browser.py`; `pyrate-limiter` (unused) |

Authority ceiling for everything adopted: **unit-test + fixture**. No live ATS
or browser receipt binds this snapshot to production behaviour.

---

## 8. Citation greps (path:symbol)

```
scraper/user_agents.py:22:def pick_ua()
scraper/browser.py:54:async def browser_session
scraper/browser.py:67:launch_persistent_context
scraper/browser.py:75:--disable-blink-features=AutomationControlled
scraper/http_client.py:190:async def get_json
scraper/http_client.py:221:stop=stop_after_attempt(4)
scraper/http_client.py:222:wait=wait_exponential_jitter(initial=1, max=30)
scraper/http_client.py:268:impersonate: str = "chrome124"
scraper/db.py:165:def upsert_job
scraper/db.py:540:def is_breaker_open
scraper/fetchers/__init__.py:26:def resolve_fetcher
scraper/liveness.py:81:def classify
scraper/filters.py:613:def filter_jobs
scraper/discover.py:20:def slug_candidates
scraper/runner.py:105:async def run_fetch
```

---

## 9. Dependencies and license (Job Scraper slice)

| Dep | Declared | Used? | Searcher |
|---|---|---|---|
| `httpx[http2]` | yes | yes | justified for honest HTTP/2 |
| `tenacity` | yes | `get_json` only | justified or replaceable with a 30-line retry |
| `pydantic` | yes | models | optional; Searcher models may differ |
| `PyYAML` | yes | companies file | only if Searcher keeps YAML manifests |
| `structlog` | yes | logging | replaceable with stdlib / Searcher log |
| `playwright` | yes | browser.py + custom fetchers | **do not take** with stealth; defer honest render |
| `tf-playwright-stealth` | yes | intended; import currently broken at 1.2.0 | **REJECT** |
| `curl_cffi` | yes | `get_html` | **REJECT** |
| `pyrate-limiter` | yes | **never imported** | do not add |
| `pytest` / `pytest-asyncio` / `respx` | dev | pytest used; respx unused | test-only |

License: MIT **declared** in `pyproject.toml`. No SPDX file. Authors field
`Josh`. Provenance for any port: this content digest, 2026-08-16.

---

## 10. What Searcher still has to build (donor does not provide)

- Persistent URL/query frontier with priority, cursors, and resume (§15.1, §15.6)
- Discovery ≠ fetch ≠ parse ≠ normalize ≠ verify
- Cheap-first escalation including a real response cache
- URL canonicalization and listing-family dedup
- Generic structured-data / OG / selector extraction
- Honest status: blocked ≠ empty
- Progress events for the results drawer
- Cooperative cancellation
- Source policy / robots / terms as first-class admits
- Any clothing/footwear source adapter
