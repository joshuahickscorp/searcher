#!/usr/bin/env bash
# Serve the Searcher API so a friend can point the GitHub Pages UI at it.
# Default bind is loopback. --lan and --tunnel are opt-in and unauthenticated.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="local"
PORT="${SEARCHER_API_PORT:-8765}"
HOST="127.0.0.1"
PAGES_URL="${SEARCHER_PAGES_URL:-https://<your-github-pages-host>/}"
PAGES_ORIGIN="${SEARCHER_PAGES_ORIGIN:-}"

usage() {
  cat <<'EOF'
Usage: scripts/serve_shared.sh [--lan | --tunnel] [--port N] [--host ADDR]

  (default)  Bind 127.0.0.1. Only this Mac can reach the API.
  --lan      Bind the local network interface and print the URL to share
             on the same network.
  --tunnel   Use cloudflared if it is already installed, print the public
             URL, and refuse if cloudflared is missing. Does not install
             anything, does not create an account, does not sign anyone up.

  --port N   Listen port (default 8765, or SEARCHER_API_PORT).
  --host A   Override bind address (ignored by --lan / --tunnel).
  --help     This message.

WARNING: This alpha has no authentication.
--lan and --tunnel expose an unauthenticated API to whoever has the URL.
Do not treat a tunnel URL as a private or secret-safe service.

The Pages UI is opened with ?api=<this-api-origin>. CORS is set from the
chosen mode; it is not widened permanently in the process defaults.

Tell friends the API is live by sending them the printed ?api= URL.
When you stop this process, it is not live — tell them that too.
GET /v1/health is the machine check: unreachable means down; HTTP 200
with status=ok means up; status=degraded means up with a blocked lane.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --lan)
      MODE="lan"
      shift
      ;;
    --tunnel)
      MODE="tunnel"
      shift
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" == "lan" && "$MODE" == "tunnel" ]]; then
  echo "choose one of --lan or --tunnel" >&2
  exit 2
fi

lan_ip() {
  local ip=""
  ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
  if [[ -z "$ip" ]]; then
    ip="$(ipconfig getifaddr en1 2>/dev/null || true)"
  fi
  if [[ -z "$ip" ]]; then
    ip="$(ipconfig getifaddr en2 2>/dev/null || true)"
  fi
  printf '%s' "$ip"
}

DEFAULT_ORIGINS="http://127.0.0.1:${PORT},http://localhost:${PORT},http://127.0.0.1:8080,http://localhost:8080,http://127.0.0.1:8000,http://localhost:8000"
ORIGINS="$DEFAULT_ORIGINS"
if [[ -n "$PAGES_ORIGIN" ]]; then
  ORIGINS="${ORIGINS},${PAGES_ORIGIN}"
fi

echo
echo "WARNING: This alpha has no authentication."
echo "Whoever can reach the printed URL can create searches, read results,"
echo "and cancel or delete campaigns. --lan and --tunnel are opt-in."
echo

SHARE_URL=""
BIND_HOST="$HOST"

case "$MODE" in
  local)
    BIND_HOST="127.0.0.1"
    SHARE_URL="http://127.0.0.1:${PORT}"
    echo "Mode: local (loopback only)."
    ;;
  lan)
    IP="$(lan_ip)"
    if [[ -z "$IP" ]]; then
      echo "could not determine a LAN address (tried en0/en1/en2)" >&2
      exit 1
    fi
    BIND_HOST="$IP"
    SHARE_URL="http://${IP}:${PORT}"
    ORIGINS="${ORIGINS},http://${IP}:${PORT}"
    echo "Mode: lan. Binding ${BIND_HOST}:${PORT}."
    echo "Anyone on this network who has the URL can use the unauthenticated API."
    ;;
  tunnel)
    if ! command -v cloudflared >/dev/null 2>&1; then
      echo "cloudflared is not installed."
      echo "This script will not install it, will not create an account,"
      echo "and will not sign anyone up."
      echo "Install cloudflared yourself if you want --tunnel, or use --lan"
      echo "on the same network, or run without flags for loopback only."
      exit 1
    fi
    BIND_HOST="127.0.0.1"
    SHARE_URL="http://127.0.0.1:${PORT}"
    echo "Mode: tunnel. cloudflared found. API binds loopback; tunnel is public."
    echo "Anyone with the printed tunnel URL can use the unauthenticated API."
    ;;
esac

export SEARCHER_API_HOST="$BIND_HOST"
export SEARCHER_API_PORT="$PORT"
export SEARCHER_CORS_ORIGINS="$ORIGINS"
export SEARCHER_SERVE_WEB="${SEARCHER_SERVE_WEB:-1}"
export SEARCHER_DATA_ROOT="${SEARCHER_DATA_ROOT:-$ROOT/data}"

HAND="${PAGES_URL}"
if [[ "$HAND" != */ ]]; then
  HAND="${HAND}/"
fi
# strip a trailing path-less slash doubling
FRIEND_URL="${HAND}?api=${SHARE_URL}"

echo "API origin: ${SHARE_URL}"
echo "Health:     ${SHARE_URL}/v1/health"
echo "Hand this to a friend (Pages UI against this API):"
echo "  ${FRIEND_URL}"
echo
echo "It is live while this process is running. Stop the process to take it down."
echo "Set SEARCHER_PAGES_ORIGIN to your GitHub Pages origin so the browser"
echo "is allowed to call this API. Example: https://you.github.io"
echo

if [[ "$MODE" != "tunnel" ]]; then
  exec uv run searcher serve --host "$BIND_HOST" --port "$PORT" --cors "$ORIGINS" --static
fi

# Tunnel: start the API, then cloudflared, print the public URL when it appears.
API_LOG="$(mktemp -t searcher-api.XXXXXX)"
TUN_LOG="$(mktemp -t searcher-tunnel.XXXXXX)"
cleanup() {
  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" 2>/dev/null || true
  fi
  if [[ -n "${TUN_PID:-}" ]]; then
    kill "$TUN_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

uv run searcher serve --host 127.0.0.1 --port "$PORT" --cors "$ORIGINS" --static \
  >"$API_LOG" 2>&1 &
API_PID=$!

# Wait briefly for the API to accept connections.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sf "http://127.0.0.1:${PORT}/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

cloudflared tunnel --url "http://127.0.0.1:${PORT}" --no-autoupdate >"$TUN_LOG" 2>&1 &
TUN_PID=$!

PUBLIC=""
for _ in $(seq 1 50); do
  PUBLIC="$(grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$TUN_LOG" | head -n 1 || true)"
  if [[ -n "$PUBLIC" ]]; then
    break
  fi
  if ! kill -0 "$TUN_PID" 2>/dev/null; then
    echo "cloudflared exited before printing a URL." >&2
    tail -n 20 "$TUN_LOG" >&2 || true
    exit 1
  fi
  sleep 0.2
done

if [[ -z "$PUBLIC" ]]; then
  echo "timed out waiting for a cloudflared URL." >&2
  tail -n 20 "$TUN_LOG" >&2 || true
  exit 1
fi

echo
echo "Public tunnel URL: ${PUBLIC}"
echo "Hand this to a friend:"
echo "  ${HAND}?api=${PUBLIC}"
echo
echo "WARNING again: this URL is unauthenticated. Anyone who has it can use the API."
echo

wait "$API_PID"
