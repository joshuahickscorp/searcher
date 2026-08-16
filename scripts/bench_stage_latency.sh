#!/usr/bin/env bash
# Per-stage live campaign timing. Writes artifacts/searcher-latency.receipt.json.
# Usage: scripts/bench_stage_latency.sh before|after [runs]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PHASE="${1:-before}"
RUNS="${2:-3}"
OUTPUT="${3:-$ROOT/artifacts/searcher-latency.receipt.json}"
mkdir -p "$(dirname "$OUTPUT")"
exec uv run python -m searcher.bench.stage_latency --phase "$PHASE" --runs "$RUNS" --output "$OUTPUT"
