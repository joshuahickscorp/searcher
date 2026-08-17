#!/usr/bin/env bash
# Local API entry point. Binds 127.0.0.1:8765 and serves web/ so the UI
# works with the default empty API_BASE in web/config.js.
# For lanes, weights, and a first search, use scripts/first_run.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST="${SEARCHER_API_HOST:-127.0.0.1}"
PORT="${SEARCHER_API_PORT:-8765}"
export SEARCHER_API_HOST="$HOST"
export SEARCHER_API_PORT="$PORT"
export SEARCHER_SERVE_WEB="${SEARCHER_SERVE_WEB:-1}"
export SEARCHER_DATA_ROOT="${SEARCHER_DATA_ROOT:-$ROOT/data}"
export SEARCHER_LIVE_DISCOVERY="${SEARCHER_LIVE_DISCOVERY:-1}"

WEIGHTS_INSTALL="uv run --extra vision python scripts/prepare_embedding_weights.py"

port_listening() {
  local host="$1" port="$2"
  python3 -c "import socket; s=socket.socket(); s.settimeout(0.3); r=s.connect_ex(('$host', int('$port'))); s.close(); raise SystemExit(0 if r==0 else 1)"
}

if port_listening "$HOST" "$PORT"; then
  echo "address already in use: ${HOST}:${PORT}" >&2
  echo "Pick another port:" >&2
  echo "  SEARCHER_API_PORT=8766 ./scripts/run_api.sh" >&2
  exit 1
fi

weights=""
if [[ -n "${SEARCHER_EMBEDDING_WEIGHTS:-}" && -f "${SEARCHER_EMBEDDING_WEIGHTS}" ]]; then
  weights="$SEARCHER_EMBEDDING_WEIGHTS"
elif [[ -f "${SEARCHER_DATA_ROOT}/models/embedding.pt" ]]; then
  weights="${SEARCHER_DATA_ROOT}/models/embedding.pt"
elif [[ -f "${SEARCHER_DATA_ROOT}/models/clip.pt" ]]; then
  weights="${SEARCHER_DATA_ROOT}/models/clip.pt"
fi

echo
echo "Searcher local API"
echo "------------------"
echo "Interface: http://${HOST}:${PORT}/"
echo "Health:    http://${HOST}:${PORT}/v1/health"
echo
if [[ -z "$weights" ]]; then
  echo "Learned visual backbone: not present."
  echo "Matching uses classical descriptors. Nothing is promoted to Real"
  echo "through a missing-weight fallback."
else
  echo "Learned visual backbone: a weights file is present at ${weights}."
  echo "Availability is a successful probe, not file existence."
fi
echo "Install with:"
echo "  ${WEIGHTS_INSTALL}"
echo
echo "Next:"
echo "  Open http://${HOST}:${PORT}/"
echo "  Or run ./scripts/first_run.sh to see which lanes are live and to"
echo "  run a first search."
echo "  One photograph is enough. A first live search can take a couple"
echo "  of minutes. Empty public lists are allowed."
echo
echo "This process has no authentication. Only this computer can reach it."
echo "Ctrl-C stops it."
echo

exec uv run searcher serve --static
