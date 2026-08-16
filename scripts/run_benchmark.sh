#!/usr/bin/env bash
# Regenerates the public benchmark receipt and the evidence board.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python -m benchmark.run --all
