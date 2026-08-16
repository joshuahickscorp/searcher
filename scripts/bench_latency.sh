#!/usr/bin/env bash
# Measure Searcher latency on this host. Writes artifacts/searcher-performance.receipt.json.
# Does not tune the system to the target. Reports the number either way.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUTPUT="${1:-$ROOT/artifacts/searcher-performance.receipt.json}"
mkdir -p "$(dirname "$OUTPUT")"
exec uv run python -m searcher.bench --output "$OUTPUT"
