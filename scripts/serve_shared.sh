#!/usr/bin/env bash
# Serve the Searcher API so a friend can reach it.
# Default bind is loopback. --lan and --tunnel are opt-in and unauthenticated.
# Refuses early when a printed URL could not work. Verifies CORS, the port,
# and that the printed URL answers before calling it live.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MODE="local"
CHECK_ONLY=0
PORT="${SEARCHER_API_PORT:-8765}"
HOST="127.0.0.1"
PAGES_URL="${SEARCHER_PAGES_URL:-https://<your-github-pages-host>/}"
PAGES_ORIGIN="${SEARCHER_PAGES_ORIGIN:-}"
LAN_SET=0
TUNNEL_SET=0

usage() {
  cat <<'EOF'
Usage: scripts/serve_shared.sh [--lan | --tunnel] [--port N] [--host ADDR] [--check]

  (default)  Bind 127.0.0.1. Only this Mac can reach the API.
  --lan      Bind the local network interface and print the URL to share
             on the same network.
  --tunnel   Use cloudflared if it is already installed, print the public
             URL, and refuse if cloudflared is missing. Does not install
             anything, does not create an account, does not sign anyone up.

  --port N   Listen port (default 8765, or SEARCHER_API_PORT).
  --host A   Override bind address (ignored by --lan / --tunnel).
  --check    Check port, CORS, and the URL that would be printed. Do not
             start the API.
  --help     This message.

WARNING: This alpha has no authentication.
--lan and --tunnel expose an unauthenticated API to whoever has the URL.
Do not treat a tunnel URL as a private or secret-safe service.

The Pages UI is opened with ?api=<this-api-origin> only when the API
origin is HTTPS and SEARCHER_PAGES_ORIGIN is set. CORS is set from the
chosen mode; it is not widened permanently in the process defaults.

Tell friends the API is live by sending them a URL this script has
verified. When you stop this process, it is not live — tell them that too.
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
      LAN_SET=1
      shift
      ;;
    --tunnel)
      MODE="tunnel"
      TUNNEL_SET=1
      shift
      ;;
    --check)
      CHECK_ONLY=1
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

if [[ "$LAN_SET" -eq 1 && "$TUNNEL_SET" -eq 1 ]]; then
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

port_listening() {
  local host="$1" port="$2"
  python3 -c "import socket; s=socket.socket(); s.settimeout(0.3); r=s.connect_ex(('$host', int('$port'))); s.close(); raise SystemExit(0 if r==0 else 1)"
}

pages_url_usable() {
  local url="$1"
  if [[ -z "$url" ]]; then
    return 1
  fi
  if [[ "$url" == *'<'* || "$url" == *'>'* || "$url" == *your-github-pages-host* ]]; then
    return 1
  fi
  if [[ "$url" != https://* ]]; then
    return 1
  fi
  return 0
}

origin_is_origin_only() {
  local origin="$1"
  local rest="${origin#*://}"
  if [[ "$origin" != http://* && "$origin" != https://* ]]; then
    return 1
  fi
  if [[ -z "$rest" || "$rest" == */* ]]; then
    return 1
  fi
  return 0
}

DEFAULT_ORIGINS="http://127.0.0.1:${PORT},http://localhost:${PORT},http://127.0.0.1:8080,http://localhost:8080,http://127.0.0.1:8000,http://localhost:8000"
ORIGINS="$DEFAULT_ORIGINS"
if [[ -n "$PAGES_ORIGIN" ]]; then
  if ! origin_is_origin_only "$PAGES_ORIGIN"; then
    echo "SEARCHER_PAGES_ORIGIN must be the origin only (scheme + host), not a path." >&2
    echo "Example: https://joshuahickscorp.github.io" >&2
    echo "Not:     https://joshuahickscorp.github.io/searcher/" >&2
    exit 1
  fi
  ORIGINS="${ORIGINS},${PAGES_ORIGIN}"
fi

SHARE_URL=""
BIND_HOST="$HOST"
PAGES_FRIEND=""

case "$MODE" in
  local)
    BIND_HOST="127.0.0.1"
    SHARE_URL="http://127.0.0.1:${PORT}"
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
    ;;
esac

# A Pages ?api=http://… URL cannot work (mixed content). Refuse to print one.
if pages_url_usable "$PAGES_URL"; then
  if [[ "$MODE" != "tunnel" ]]; then
    if [[ -n "$PAGES_ORIGIN" || -n "${SEARCHER_PAGES_URL:-}" ]]; then
      echo "Refusing to print a Pages URL. An HTTPS page cannot call this HTTP API" >&2
      echo "(mixed content). Send the API origin itself for local and LAN use," >&2
      echo "or use --tunnel so the API origin is HTTPS." >&2
    fi
  elif [[ -z "$PAGES_ORIGIN" ]]; then
    echo "Refusing to print a Pages URL. SEARCHER_PAGES_ORIGIN is not set, so the" >&2
    echo "published page would be refused by CORS and look unavailable." >&2
    echo "Set SEARCHER_PAGES_ORIGIN to the origin only (scheme + host), for example" >&2
    echo "https://joshuahickscorp.github.io" >&2
  else
    HAND="$PAGES_URL"
    if [[ "$HAND" != */ ]]; then
      HAND="${HAND}/"
    fi
    # Filled in after the tunnel URL is known.
    PAGES_FRIEND="pending"
  fi
fi

LISTEN_HOST="$BIND_HOST"
if [[ "$MODE" == "tunnel" ]]; then
  LISTEN_HOST="127.0.0.1"
fi

if port_listening "$LISTEN_HOST" "$PORT"; then
  echo "address already in use: ${LISTEN_HOST}:${PORT}" >&2
  echo "Refusing to start. A printed URL on this port would not be this process." >&2
  echo "Pick another port:" >&2
  echo "  SEARCHER_API_PORT=8766 ./scripts/serve_shared.sh" >&2
  exit 1
fi

echo
echo "WARNING: This alpha has no authentication."
echo "Whoever can reach the printed URL can create searches, read results,"
echo "and cancel or delete campaigns. --lan and --tunnel are opt-in."
echo

case "$MODE" in
  local)
    echo "Mode: local (loopback only)."
    ;;
  lan)
    echo "Mode: lan. Binding ${BIND_HOST}:${PORT}."
    echo "Anyone on this network who has the URL can use the unauthenticated API."
    ;;
  tunnel)
    echo "Mode: tunnel. cloudflared found. API binds loopback; tunnel is public."
    echo "Anyone with the printed tunnel URL can use the unauthenticated API."
    ;;
esac

echo "API origin that will be verified: ${SHARE_URL}"
if [[ "$MODE" == "local" || "$MODE" == "lan" ]]; then
  echo "Send that origin. It also serves the interface. Do not send a Pages"
  echo "?api=http://… URL — the browser refuses that combination."
fi
echo "CORS allowlist: ${ORIGINS}"
echo

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  echo "Check only. Port is free. CORS allowlist is set for this mode."
  echo "Nothing was started."
  exit 0
fi

export SEARCHER_API_HOST="$BIND_HOST"
export SEARCHER_API_PORT="$PORT"
export SEARCHER_CORS_ORIGINS="$ORIGINS"
export SEARCHER_SERVE_WEB="${SEARCHER_SERVE_WEB:-1}"
export SEARCHER_DATA_ROOT="${SEARCHER_DATA_ROOT:-$ROOT/data}"

verify_answers() {
  local url="$1"
  if ! curl -sf --max-time 3 "${url}/v1/health" >/dev/null; then
    echo "Printed URL did not answer: ${url}/v1/health" >&2
    return 1
  fi
  if ! curl -sf --max-time 3 "${url}/" >/dev/null; then
    echo "Interface did not answer: ${url}/" >&2
    return 1
  fi
  return 0
}

verify_cors() {
  local url="$1" origin="$2"
  if [[ -z "$origin" ]]; then
    return 0
  fi
  local headers
  headers="$(curl -sD - -o /dev/null --max-time 3 -H "Origin: ${origin}" "${url}/v1/health" || true)"
  if ! printf '%s' "$headers" | grep -qi "access-control-allow-origin: ${origin}"; then
    echo "CORS check failed: ${origin} is not allowed by ${url}" >&2
    echo "The published page would say the search service is unavailable." >&2
    return 1
  fi
  return 0
}

API_PID=""
TUN_PID=""
API_LOG=""
TUN_LOG=""

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then
    kill "$API_PID" 2>/dev/null || true
  fi
  if [[ -n "${TUN_PID:-}" ]]; then
    kill "$TUN_PID" 2>/dev/null || true
  fi
}

start_api() {
  local bind="$1"
  API_LOG="$(mktemp -t searcher-api.XXXXXX)"
  uv run searcher serve --host "$bind" --port "$PORT" --cors "$ORIGINS" --static \
    >"$API_LOG" 2>&1 &
  API_PID=$!
  local _
  for _ in $(seq 1 40); do
    if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/v1/health" >/dev/null 2>&1; then
      return 0
    fi
    if [[ "$bind" != "127.0.0.1" ]] && curl -sf --max-time 2 "http://${bind}:${PORT}/v1/health" >/dev/null 2>&1; then
      return 0
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
      echo "API exited before becoming reachable." >&2
      tail -n 40 "$API_LOG" >&2 || true
      return 1
    fi
    sleep 0.25
  done
  echo "timed out waiting for the API on port ${PORT}." >&2
  tail -n 40 "$API_LOG" >&2 || true
  return 1
}

print_verified() {
  local url="$1"
  echo
  echo "Verified. This URL answers:"
  echo "  ${url}/"
  echo "Health:"
  echo "  ${url}/v1/health"
  if [[ -n "${2:-}" ]]; then
    echo "Hand this to a friend (Pages UI against this HTTPS API):"
    echo "  ${2}"
  fi
  echo
  echo "It is live while this process is running. Stop the process to take it down."
  echo
}

if [[ "$MODE" != "tunnel" ]]; then
  trap cleanup EXIT INT TERM
  start_api "$BIND_HOST"
  if ! verify_answers "$SHARE_URL"; then
    exit 1
  fi
  if [[ -n "$PAGES_ORIGIN" ]]; then
    if ! verify_cors "$SHARE_URL" "$PAGES_ORIGIN"; then
      exit 1
    fi
    echo "CORS: ${PAGES_ORIGIN} is allowed. The published HTTPS page still cannot"
    echo "call this HTTP API (mixed content). Send the API origin above."
  fi
  print_verified "$SHARE_URL"
  wait "$API_PID"
  exit $?
fi

# Tunnel: start the API, then cloudflared, print the public URL when it appears.
trap cleanup EXIT INT TERM
start_api "127.0.0.1"
if ! verify_answers "http://127.0.0.1:${PORT}"; then
  exit 1
fi
if [[ -n "$PAGES_ORIGIN" ]]; then
  if ! verify_cors "http://127.0.0.1:${PORT}" "$PAGES_ORIGIN"; then
    exit 1
  fi
fi

TUN_LOG="$(mktemp -t searcher-tunnel.XXXXXX)"
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

if ! verify_answers "$PUBLIC"; then
  echo "The printed tunnel URL did not answer." >&2
  exit 1
fi

FRIEND=""
if [[ "$PAGES_FRIEND" == "pending" ]]; then
  HAND="$PAGES_URL"
  if [[ "$HAND" != */ ]]; then
    HAND="${HAND}/"
  fi
  FRIEND="${HAND}?api=${PUBLIC}"
fi

echo
echo "Public tunnel URL: ${PUBLIC}"
print_verified "$PUBLIC" "$FRIEND"
echo "WARNING again: this URL is unauthenticated. Anyone who has it can use the API."
echo

wait "$API_PID"
