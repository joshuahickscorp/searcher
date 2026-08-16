# Donor setup — VisionMCP

Searcher's perception lane calls VisionMCP through a Searcher-owned adapter. The
donor is pinned to SHA `18ee3c06d27f04937d1681dea5fa2650131e4b2a`
(`visionmcp-ocular` 0.8.0a2) and is **not** declared in `pyproject.toml`.

Install it:

```bash
scripts/setup_donor.sh
```

## Why it is not a normal dependency

Two reasons, both observed rather than assumed:

1. **Not published.** `visionmcp-ocular` is not on PyPI, so there is no version
   to resolve.
2. **`git+https` install of the audited SHA fails.** That commit records a
   gitlink at `artifacts/world-engine/step-28/hostile-pack-fixture` with no
   entry in `.gitmodules`, so any submodule-recursing checkout aborts with:

   ```
   fatal: no submodule mapping found in .gitmodules for path 'artifacts/world-engine/step-28/hostile-pack-fixture'
   ```

   Cloning with `--no-recurse-submodules` works. This is a defect in the donor
   repository, not in Searcher; it is worth reporting upstream, but Searcher
   does not modify the donor to work around it.

Declaring an absolute local path in `[tool.uv.sources]` would also bake a
developer's home directory into the repository, which the public-tree scrub
(Bible §36.3) forbids. The script takes `SEARCHER_DONOR_DIR` instead.

## Without the donor

Searcher runs. `searcher capabilities` reports `importable: False`, the donor-
backed lanes report blocked, and `promotion_blocked` is set so nothing can be
promoted to Real through a degraded path. The donor-bound tests skip rather
than pass vacuously.
