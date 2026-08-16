# Module map

Bible §34 describes a multi-package tree (`packages/core`, `packages/campaigns`, …).
Searcher implements those packages as submodules of one installable distribution
named `searcher`, in src layout:

| Bible path | Implemented path |
|---|---|
| `packages/core/` | `src/searcher/core/` |
| `packages/campaigns/` | `src/searcher/campaigns/` |
| `packages/evidence/` | `src/searcher/evidence/` |
| `packages/storage/` (implied by §27 / §35) | `src/searcher/storage/` |
| `packages/receipts/` | `src/searcher/receipts/` |
| `packages/contracts/` | `src/searcher/contracts/` |

File names inside each package match Bible §35 (`config.py`, `ids.py`,
`controller.py`, `content_store.py`, …). Contract model names match Bible §9
exactly.

This is a documented choice, not a silent narrowing: one distribution, no path
hacks, identical module names under `searcher.*`. Later waves add
`searcher.hypotheses`, `searcher.queries`, `searcher.sources`, and the rest the
same way. They do not invent a second packaging layout.

`migrations/` and `fixtures/` stay at the repository root, as §34 draws them.
The CLI entry point is `searcher` → `searcher.cli:main`.
