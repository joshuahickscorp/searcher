# Searcher Phase Zero — Source Authority

Inspection date (UTC): 2026-08-16T04:48:46Z  
Inspector: Searcher Phase Zero audit (read-only)  
Standing authority: `docs/SEARCHER_FULL_IMPLEMENTATION_BIBLE.md` §4  
Pinned VisionMCP SHA required by the task contract:
`18ee3c06d27f04937d1681dea5fa2650131e4b2a`

This document records **what was observed on this host**, what donor
documents **report**, and what this audit **infers**. A README or ledger
claim is not evidence that code ran.

No donor checkout was mutated. `<home>/Downloads/visionmcp`
was read only via non-mutating git commands. The pinned clone at
`<home>/.searcher-donors/visionmcp` was read only.

---

## 0. Authority decision (read this first)

| Role | Path | Git | SHA | Decision |
| --- | --- | --- | --- | --- |
| **Authoritative VisionMCP donor** | `<home>/.searcher-donors/visionmcp` | detached HEAD, clean, `origin` = `git@github.com:joshuahickscorp/visionmcp.git` | `18ee3c06d27f04937d1681dea5fa2650131e4b2a` (`v0.8.0-alpha.2`, equals `origin/main`) | **ACCEPT as the sole VisionMCP authority for Searcher** |
| User working VisionMCP checkout | `<home>/Downloads/visionmcp` | `main`, **clean**, same SHA, many extra local branches and 8 attached worktrees | `18ee3c06d27f04937d1681dea5fa2650131e4b2a` | **Same commit as the pin.** Do not write. Do not treat newer worktrees as authority. |
| Job Scraper (found) | `<home>/Desktop/jobscraper` | **not a git repository** | none | **FOUND — this changes the supervising engineer's "not located" result.** Not an authoritative frozen donor. See §3 and `JOB_SCRAPER_CAPABILITY_HARVEST.md`. |
| Historical Job Scraper path | `<home>/Downloads/jobscraper` | absent | — | README inside the Desktop tree still names this path. **Observed absent.** |
| MTP | (no tree) | — | — | **ABSENT.** Searcher's campaign controller covers Bible §7. |
| Searcher product repo | `<home>/Downloads/searcher` | `main`, no remotes, clean at seed | `15602d7b6d02150835b74070126435adba73a90f` | This product. Not a donor. |
| This audit worktree | `<home>/.claude-grok/worktrees/searcher-donor-audit-20260816-003933` | `grok/searcher-donor-audit-20260816-003933` | same seed SHA | Audit outputs only. |

**Basis.** Authority is by reachable git identity and capability, not
folder mtime. The pinned clone and the user's `Downloads/visionmcp`
`main` tip are the same SHA. That SHA is tagged `v0.8.0-alpha.2` and
matches `origin/main` in the pinned clone's local remotes. Experimental
VisionMCP worktrees exist at other SHAs; several are dirty. They are
not donors for Searcher.

**Loud change from the task brief.** Job Scraper is **not** missing. It
lives on the Desktop as an unversioned personal internship scraper. It
is still not a frozen git donor, and it contains Bible §6.10-rejected
mechanisms. Searcher must **reimplement** acquisition from Bible §6 /
§15, informed by this tree, and **reject** stealth / TLS impersonation /
proxy rotation / persistent profiles.

---

## 1. Locate evidence

Searches were bounded (`find $HOME -maxdepth 3` / `4` / `5` with
`Library`, `.Trash`, `node_modules`, `.venv`, `.git` pruned). An
unbounded `find $HOME` was not run. A first `*mtp*` scan hung and was
killed; exact-name `mtp`/`MTP` scans replaced it.

### 1.1 Development roots

`<home>/Downloads` contains (product-relevant): `searcher`,
`visionmcp`, `hawking`, `merc`, `forge`, `census`. No `jobscraper`, no
`mtp`.

`<home>/Desktop` contains `jobscraper` and `substrate`.

`<home>/.searcher-donors` contains only `visionmcp`.

Vanished clone paths named by old Grok sessions — all **ABSENT**:

```text
<home>/Downloads/visionmcp-visual-compiler-lab
<home>/Downloads/visionmcp-perf
<home>/Downloads/visionmcp-world-engine
<home>/Downloads/visionmcp-public-alpha
<home>/Downloads/visionmcp-final-expansion
<home>/Downloads/visionmcp-authority
<home>/Downloads/visionmcp-authority-worktrees
<home>/Downloads/jobscraper
<home>/Downloads/mtp
<home>/Downloads/MTP
<home>/Desktop/mtp
<home>/Documents/mtp
<home>/Documents/visionmcp
<home>/Documents/jobscraper
<home>/Documents/searcher
```

### 1.2 Name-matched directories (maxdepth 3)

Observed matches included:

- `<home>/.searcher-donors/visionmcp` — pinned donor
- `<home>/Downloads/visionmcp` — user working checkout
- `<home>/Downloads/searcher` — product
- `<home>/.claude-grok/worktrees/searcher-donor-audit-20260816-003933`
- `<home>/.claude-grok/worktrees/searcher-wave1-20260816-003934`
- `<home>/Desktop/jobscraper` — **Job Scraper working tree**
- `<home>/.claude/projects/-Users-<user>-Downloads-jobscraper` — stale Claude memory only
- `<home>/.visionmcp` — runtime project store (`projects/{binary-analyses,assurance,compiler}`), not a clone
- `<home>/Downloads/forge/.visionmcp` — Forge-local state
- `<home>/hawking-preservation/stray-visionmcp-from-grok-worktree/{visionmcp-h008,_visionmcp_h008}` — historical stray clones
- Grok session directories under `~/.grok/sessions/` that *name* vanished clones
- Claude ultragoal directories under `~/.claude/ultragoal/visionmcp-*`

`*scraper*` at maxdepth 4: only `Desktop/jobscraper` and the Claude
project memory directory.

Exact-name `mtp`/`MTP` under Downloads, Desktop, Documents, Archives,
`.searcher-donors`, `.claude-grok`, `hawking-preservation`, hawking,
merc, forge, substrate, census: **no product tree**. The only hit was
an unrelated hashed JS asset
`Downloads/forge/dist/assets/03-goroutines-channels-DMtpM9fY.js`.

### 1.3 Network / `gh` search

Not run. The task contract forbids external network access. The
supervising engineer's `gh repo list` / GitHub search for Job Scraper
is therefore **unverified here**. Local inspection is sufficient to
overturn "not on this host."

---

## 2. Git truth (Bible §4.2)

### 2.1 Pinned VisionMCP — AUTHORITATIVE

| Field | Observed |
| --- | --- |
| Absolute path | `<home>/.searcher-donors/visionmcp` |
| Repository root | same (own `.git`) |
| Remotes | `origin` `git@github.com:joshuahickscorp/visionmcp.git` (fetch/push) |
| Default branch | `refs/remotes/origin/HEAD` → `origin/main` |
| Current branch | detached HEAD |
| HEAD SHA | `18ee3c06d27f04937d1681dea5fa2650131e4b2a` |
| origin/main SHA | `18ee3c06d27f04937d1681dea5fa2650131e4b2a` |
| origin/release SHA | `ce8c056a3d5b04faaf745c2a130db7efbd7ce27e` (older) |
| Dirty | **clean** (`status --porcelain` empty) |
| Staged | none |
| Untracked load-bearing | none (`ls-files --others --exclude-standard` empty) |
| Worktrees | this path only |
| Tags (this clone) | `v0.8.0-alpha.1`, `v0.8.0-alpha.2` |
| `describe` | `v0.8.0-alpha.2` |
| Package | `visionmcp-ocular` `0.8.0a2`, `requires-python >=3.11`, Apache-2.0 |
| Import / CLI | import `visionmcp`; scripts `visionmcp`, `visionmcp-dev` |
| Local branches | `main` (same SHA), remotes `origin/main`, `origin/release`, `origin/codex/world-engine` |

Recent log (observed):

```text
18ee3c0 Lock the public alpha artifacts
41ee06e Freeze evidence at the public alpha SHA
c76d9af Document the companion wheel the release gate never built
1e19809 Ship the licence, and fix the gate that should have caught its absence
98646c8 Build the missing cross-world hops, a prompt-reading controller, and four backlog fixes
```

**Reported, not re-run.** `artifacts/alpha/ALPHA_ARTIFACT_LOCK.json`
binds `true_alpha_implementation_sha` `41ee06ef…` (parent of HEAD) and
claims suite `1696 passed / 46 skipped`.
`artifacts/capability-ledger.json` still labels the product
`0.8.0a1`. Those are donor-document claims at this tree; this audit
did not run pytest or rebuild wheels.

### 2.2 User working VisionMCP — SAME SHA, DO NOT TOUCH

| Field | Observed |
| --- | --- |
| Absolute path | `<home>/Downloads/visionmcp` |
| HEAD | `18ee3c06d27f04937d1681dea5fa2650131e4b2a` on `main` |
| Dirty | **clean** before and after this audit |
| Remotes | same `origin` as the pin |
| Extra tags not in the pin | `v0.8.0a2-macos-alpha` → `c26640a8…`; `v0.8.0a2-macos-alpha-r2` → `a56a9203…`; `world-engine-authority-v1` → `4ab11ae6…`; `world-engine-baseline-ce8c056` → `ce8c056a…` |
| Local branches | many `grok/*`, `import/*`, `codex/world-engine`, `fidelity-apply`, etc. |

Attached worktrees (observed via `git worktree list`):

| Path | HEAD | Branch | Dirty? |
| --- | --- | --- | --- |
| `Downloads/visionmcp` | `18ee3c06` | `main` | clean |
| `…/bind-spatial-20260816-000448` | `18ee3c06` | `grok/bind-spatial-…` | **DIRTY** (intent/subject files) |
| `…/bind-web-20260816-000447` | `18ee3c06` | `grok/bind-web-…` | **DIRTY** (acquisition/intent) |
| `…/dead-tests-20260814-213842` | `5c3c7395` | `grok/dead-tests-…` | not used |
| `…/dead-weight-20260814-213910` | `5c3c7395` | `grok/dead-weight-…` | not used |
| `…/refactor-constraints-20260815-140212` | `c26640a8` | `grok/refactor-constraints-…` | not used |
| `…/refactor-plan-20260815-135153` | `c26640a8` | `grok/refactor-plan-…` | not used |
| `…/subject-spatial-20260815-235335` | `3e812e6a` | `grok/subject-spatial-…` | untracked `diff.patch` |
| `…/subject-web-20260815-235333` | `df0cd6b3` | `grok/subject-web-…` | untracked `diff.patch` |

**Untouchable dirty trees:** bind-spatial, bind-web, and the hawking
preservation clone below. They are not authority.

### 2.3 Hawking-preservation stray VisionMCP clones — NOT AUTHORITY

| Path | HEAD | Branch | Dirty | Remote |
| --- | --- | --- | --- | --- |
| `…/visionmcp-h008` | `2a0ca01f5cf2b60d5680ef193b984cb433aba9c0` | `grok/h008-near4-from-sandbox` | clean | local path to a vanished `.worktrees/world-engine` |
| `…/_visionmcp_h008` | `47255a33c09c0d5001dcbc1ec280ecc25d4961cf` | `codex/world-engine` | **29 dirty paths** | `Downloads/visionmcp` |

These are older than `18ee3c06`. The dirty clone is frozen-as-found.

### 2.4 Searcher

| Field | Observed |
| --- | --- |
| Canonical checkout | `<home>/Downloads/searcher` |
| HEAD | `15602d7b6d02150835b74070126435adba73a90f` |
| Branch | `main` |
| Remotes | **none** |
| Tags | none |
| Worktrees | this audit worktree; `searcher-wave1-20260816-003934` (concurrent, not read for product code) |
| Dirty (canonical) | clean at inspection |

### 2.5 Job Scraper — FOUND, UNVERSIONED

| Field | Observed |
| --- | --- |
| Path | `<home>/Desktop/jobscraper` |
| Git | **no `.git`** |
| Package | `jobscraper` `0.1.0` in `pyproject.toml`; `requires-python >=3.11`; license **text** `MIT` (no `LICENSE` file) |
| Entry point | `scraper = scraper.cli:main` |
| README self-path | still says `cd <home>/Downloads/jobscraper` |
| Tests (counted, not run) | 10 `test_*.py`, 232 `def test_` |
| Personal / load-bearing untracked-equivalent | `cv/` (CVs), `data/jobs.db` (+ wal/shm), `jobs.db`, `.venv/`, `data/profiles/` (Playwright profiles) |
| Claude memory | `~/.claude/projects/-Users-<user>-Downloads-jobscraper/memory/` — CVs and an unrelated Hawking scrub; **not** scrape-engine docs |

### 2.6 MTP

No repository, directory, or Claude project named MTP/mtp. Optional
donor, absent.

### 2.7 Running processes

`ps` was denied by the sandbox (`operation not permitted`). No claim is
made about live processes using these checkouts.

---

## 3. Capability-by-capability authority (Bible §4.3)

For VisionMCP at `18ee3c06`:

| Question | Answer |
| --- | --- |
| Reachable? | Yes. Source tree + declared installable distribution `visionmcp-ocular`. |
| Packaged? | **Reported.** Two-wheel split: core `visionmcp-ocular` and companion `visionmcp-ocular-kernels`. Production PyPI is **not** claimed as published (`README.md`). Install path is git+SHA or a local wheel. This audit did not build or install. |
| Stable API / CLI / MCP? | Yes, in-tree. Public CLI `visionmcp.cli.public:main`. Core MCP 15 tools in `visionmcp.mcp.core_server` / `profiles.CORE_TOOLS`. Wire versions in `visionmcp.api`. |
| Tests? | **Reported.** 132 `test_*.py`, 1623 `def test_` counted by `rg`. ALPHA lock reports `1696 passed / 46 skipped` (parametrize inflates collected tests). **Not run.** |
| Real runtime + receipt bound to this SHA? | Mixed. `18ee3c06` is "Lock the public alpha artifacts." Many receipts bind **older** SHAs (`41ee06ef`, `2562502e`, `1a76eec7`). Ocular honest-baseline path cited by the ledger is **missing** from this tree. |
| Newer branch better? | **Inferred no for Searcher.** Dirty bind-* worktrees are in-flight VisionMCP work, not a better Searcher base. |

Job Scraper is reachable as source but has no SHA, so it cannot be
`REUSE_AS_PACKAGE` or `VENDOR_FROZEN_SNAPSHOT`.

---

## 4. How Searcher will invoke VisionMCP

See `REUSE_DECISIONS.md` for the full argument. Summary:

**Primary:** Searcher-owned adapter
`src/searcher/integrations/visionmcp/` wrapping an **in-process import**
of the `visionmcp` core control plane, dependency-pinned to git SHA
`18ee3c06` of distribution `visionmcp-ocular==0.8.0a2`. Lazy-import
`imaging` (numpy/Pillow) and never import kernels/torch/playwright at
adapter import time.

**Fallback:** subprocess CLI `visionmcp` (`doctor --core`,
`capabilities --json`, `receipt verify`, `artifact verify`).

**When a capability is missing:** the adapter returns a structured
unavailable/blocked record (same honesty as
`visionmcp.capabilities.capabilities_report`) and Searcher continues
the campaign. Searcher never fabricates visual evidence, match scores,
or authenticity.

MCP `visionmcp serve --profile core` is a **third, isolation-only**
option, not the product default. Core `vision.compare` is
digest-identity, not product matching. The `search` profile is not in
`PUBLIC_PROFILES` and its tools register caller-supplied records; they
do not search clothing marketplaces.

---

## 5. What to exclude from the MVP (Bible §5.15)

Do not import into Searcher MVP merely because they exist at this SHA:

- Apple-specific parity corpora / evaluators (`compiler.apple-parity04`
  status **failed**, 297/0)
- Frontend reconstruction compiler (`visionmcp.compiler`, kernels)
- Source-code repair (`visionmcp.repair` / `repairs`)
- Blender scene generation (`visionmcp.blender`)
- Full 3D reconstruction / COLMAP (`reconstruction`, plugin `colmap`)
- Fur / organic generation (`grooming`, `organic`)
- Binary analysis / Ghidra (`visionmcp.binary`)
- Private benchmark vaults / hidden evaluator artifacts
- Large generative model weights (none bundled; `models` extra is empty
  of weights; `vision.generate.authorized` is greed-gated)
- VisionMCP Studio as Searcher UI
- VisionMCP `search`/`greed` profiles as the clothing search engine
- Job Scraper stealth, TLS impersonation, proxy rotation, persistent
  browser profiles, internship ranking

---

## 6. Candidate inventory (complete)

| ID | Kind | Path | SHA / identity | Dirty | Authority |
| --- | --- | --- | --- | --- | --- |
| vmcp-pin | VisionMCP clone | `~/.searcher-donors/visionmcp` | `18ee3c06` detached | clean | **YES** |
| vmcp-user | VisionMCP checkout | `~/Downloads/visionmcp` | `18ee3c06` main | clean | same commit; do not write |
| vmcp-wt-* | VisionMCP worktrees | `~/.claude-grok/worktrees/{bind-*,dead-*,refactor-*,subject-*}` | mixed | some dirty | NO |
| vmcp-h008 | stray clone | `~/hawking-preservation/…/visionmcp-h008` | `2a0ca01f` | clean | NO |
| vmcp-h008b | stray clone | `~/hawking-preservation/…/_visionmcp_h008` | `47255a33` | **dirty** | NO |
| jobscraper-desktop | Job Scraper tree | `~/Desktop/jobscraper` | no git | n/a (live personal data) | inspect-only; not frozen |
| jobscraper-memory | Claude memory | `~/.claude/projects/-Users-<user>-Downloads-jobscraper` | n/a | n/a | not a donor |
| mtp | — | not found | — | — | absent |
| searcher | product | `~/Downloads/searcher` + worktrees | `15602d7` | this worktree writes audit only | product |

---

## 7. Claims discipline

| Claim | Kind |
| --- | --- |
| Pin and Downloads/visionmcp share SHA `18ee3c06` | **Observed** (`rev-parse`) |
| Downloads/visionmcp porcelain empty before and after | **Observed** |
| Job Scraper exists on Desktop and is not a git repo | **Observed** |
| MTP product tree absent in bounded search | **Observed** (bounded; not a proof of the entire disk) |
| `visionmcp-ocular` 0.8.0a2, Apache-2.0, zero core deps | **Observed** in `pyproject.toml` / `LICENSE` |
| 15 core MCP tools | **Observed** in `profiles.CORE_TOOLS` and `mcp/core_server.py` |
| 1696 passed tests | **Reported** by `ALPHA_ARTIFACT_LOCK.json`; **not verified** |
| Ocular proposal recall 0.648 | **Reported** by `capabilities.py` / ledger; baseline file **absent** |
| Search tools crawl the web | **False.** Observed: they register caller-supplied `records`. |
| Job Scraper is a frozen git donor | **False.** Observed: no `.git`. |
