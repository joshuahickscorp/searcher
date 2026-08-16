#!/usr/bin/env bash
# Full suite. The live-campaign test runs in its own interpreter because it
# leaves macOS unable to spawn child processes afterwards (see G039 / the
# docstring in tests/real_runtime/test_orchestrator_live.py).
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pytest -q "$@"
uv run pytest -q -m live_campaign "$@"
