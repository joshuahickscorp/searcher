# Document replacements (false sentence → shipped truth)

## ARCHITECTURE.md
- False: "The served API process today runs reference analysis and query compilation, then stops with an honest `BLOCKED` because discovery is not wired into that process. The later stages exist as packages and tests. They are not invoked by `scripts/run_api.sh`."
- True: live discovery is the `run_api.sh` default (`SEARCHER_LIVE_DISCOVERY=1`). A live campaign reaches `PARTIAL` when coverage is incomplete. `COMPLETE` requires planned coverage was searched and exhausted. Zero work is `BLOCKED` with a reason naming what was missing.

## CLAIMS.md
- False: "Matching in this tree is classical." / Not entitled: "that the engine has a learned visual backbone" / "any precision, recall, leakage, cost, or latency number" / "No public benchmark has been run" (LIMITATIONS, cited from the same lie).
- True: DINOv2 ViT-S/14 from `$SEARCHER_DATA_ROOT/models/embedding.pt`, prepared by `scripts/prepare_embedding_weights.py`, never downloaded, unavailable unless a real probe succeeds. Public receipt `artifacts/searcher-public-benchmark.receipt.json`: recall@1 0.771, recall@5 1.0, MRR 0.867 over 35 queries, false Real 0.

## LIMITATIONS.md
- False: "No learned visual backbone." / "No public benchmark has been run." / "The static UI still mentions a current benchmark. No benchmark has been run."
- True: optional local DINOv2 with a real probe; the receipt above is the cited benchmark; the UI names that receipt.

## docs/architecture/EMBEDDINGS.md
- False: "Searcher loads a local ResNet50 (`IMAGENET1K_V2`)"
- True: DINOv2 ViT-S/14 TorchScript; availability is a successful probe call, not file existence.

## docs/architecture/API.md
- False: "`SEARCHER_EMBEDDING_WEIGHTS` … this version does not load it"
- True: the path is loaded lazily on the first successful probe / embed; never downloaded.

## web/index.html
- False: "the current benchmark"
- True: names `artifacts/searcher-public-benchmark.receipt.json` and the figures in it.
