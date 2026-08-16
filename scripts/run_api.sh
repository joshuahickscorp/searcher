#!/usr/bin/env bash
# One-command local API. Binds 127.0.0.1:8765 and serves web/ so the UI
# works with the default empty API_BASE in web/config.js.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export SEARCHER_API_HOST="${SEARCHER_API_HOST:-127.0.0.1}"
export SEARCHER_API_PORT="${SEARCHER_API_PORT:-8765}"
export SEARCHER_SERVE_WEB="${SEARCHER_SERVE_WEB:-1}"
export SEARCHER_DATA_ROOT="${SEARCHER_DATA_ROOT:-$ROOT/data}"
exec uv run searcher serve --static
