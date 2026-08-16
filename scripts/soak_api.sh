#!/usr/bin/env bash
# Fifty sequential offline searches against a locally spawned API.
# Loopback only. Does not open a tunnel or contact a remote host.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pytest -q tests/real_runtime/test_api_soak.py --tb=short
if [[ -f artifacts/hardening/soak.json ]]; then
  echo "--- soak figures ---"
  cat artifacts/hardening/soak.json
fi
