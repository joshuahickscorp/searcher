# MTP — Capability Harvest

Inspection date (UTC): 2026-08-16T04:48:46Z

## Presence

**MTP is not on this host as a donor repository.**

Bounded searches (exact directory names `mtp` / `MTP` / `Mtp`, maxdepth
4, `Library` / `node_modules` / `.venv` / `.git` pruned) under
Downloads, Desktop, Documents, Archives, `$SEARCHER_DONORS_ROOT`,
`<agent-scratch>`, `<historical-stray>`, and the product trees hawking,
merc, forge, substrate, and census returned **no product tree**.

assistant projects: no `*mtp*` name. `$SEARCHER_DONORS_ROOT` contains only
`visionmcp`. A first broad `*mtp*` find over `<home>` hung and was
killed; it was replaced by the exact-name scan. The only filename hit
in product trees was an unrelated hashed Forge asset
`<unrelated-forge-checkout>/dist/assets/03-goroutines-channels-DMtpM9fY.js`.

Network / GitHub search was not run (contract).

There is therefore no git truth, no SHA, no tests, no receipts, and no
capability to adopt.

## Adoption

**DEFER** as a donor — equivalently **absent**. Do not invent an MTP
substitute.

## Why Searcher's campaign controller already covers Bible §7

Bible §7 allows optional reuse of proven MTP primitives: durable
goals, work DAGs, checkpoint/resume, worker delegation, self-grading,
stop conditions, evidence promotion, failure recovery. It forbids
inheriting unrelated domain logic, hidden global state, opaque
autonomy, unbounded retries, model-specific assumptions, or
unverifiable completion flags. The Search Campaign Controller remains
the single authority for campaign state (Bible §7 last sentence, §8.3,
§10).

Searcher will implement that controller itself:

- durable campaign state machine (Bible §10) with explicit budgets
  (§3.9) and honest stop verdicts (§23)
- checkpoint / resume / cancellation (§10.3–10.5)
- work as query families × sources × fetch attempts, not an opaque DAG
  engine
- self-grading only via evidence-bound receipts, never an unverifiable
  "done" flag
- no hidden global MTP runtime

VisionMCP's `world_brain` / `world_engine` / `orchestration` packages
exist at SHA `18ee3c06` but live on the **kernels** wheel, are aimed at
VisionMCP autonomy (one-prompt reconstruction, not product search),
and include a known concurrent-checkpoint defect (`NEXT_ALPHA_BACKLOG`
NA001). They are **DEFER** / **REJECT** as an MTP stand-in. Searcher
does not depend on them.
