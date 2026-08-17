# Searcher source authority

Bible §39 name. Draws from `docs/audit/SOURCE_AUTHORITY.md` and
`artifacts/audit/source-authority.json`. Those files record a
read-only inspection on 2026-08-16T04:48:46Z. This file binds that
inspection to git SHA `31e6004c76e1d845447e0993a5ce68948f311265`.
The inspection was not re-run in this tree: donor checkouts are
outside this repository, and this session is local-only.

Command that produced the payload:

```text
# recorded in artifacts/audit/source-authority.receipt.json
git -C $SEARCHER_DONOR_DIR rev-parse HEAD
git -C $SEARCHER_DONOR_DIR status --porcelain
```

Receipt: `artifacts/searcher-source-authority.receipt.json`.

## Authority decision

| Role | Identity | SHA | Decision |
|---|---|---|---|
| VisionMCP donor | `visionmcp-ocular` 0.8.0a2, tag `v0.8.0-alpha.2`, remote `github.com/joshuahickscorp/visionmcp` | `18ee3c06d27f04937d1681dea5fa2650131e4b2a` | Accept as the sole VisionMCP authority |
| Job Scraper | Unversioned internship scraper; frozen snapshot later taken | none | Found, not an authoritative git donor. Reimplement honest primitives. Reject Bible §6.10 evasion. |
| MTP | No product tree in the bounded locate | none | Absent. Searcher's campaign controller covers Bible §7. |
| Searcher | This repository | `31e6004c76e1d845447e0993a5ce68948f311265` (this binding). Seed SHA at inspection: `15602d7b6d02150835b74070126435adba73a90f`. | Product, not a donor. |

Job Scraper's later frozen snapshot is cited by
`src/searcher/sources/adapters/__init__.py` as manifest digest
`3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2`.
That digest is a content hash of the freeze manifest, not a git SHA.

## How Searcher invokes VisionMCP

In-process adapter under `src/searcher/integrations/visionmcp/`, lazy
import, pin checked at runtime. Missing donor reports unavailable.
VisionMCP is not in `pyproject.toml`. Install path:
`scripts/setup_donor.sh`. See `docs/architecture/DONOR_SETUP.md`.

## What is not established

- That the donor pytest suite still passes at the pin. The audit
  recorded a donor-document claim of 1696 passed / 46 skipped and did
  not run those tests.
- That any VisionMCP worktree newer than `18ee3c06` is a better
  Searcher base. Dirty experimental worktrees were observed and
  rejected as authority.
- A live re-locate of donors on this host at SHA `31e6004`. Not run.
