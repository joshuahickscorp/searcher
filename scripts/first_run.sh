#!/usr/bin/env bash
# First-run self-check for someone who has never seen this project.
# Reports lanes in operator terms, states the learned backbone, and
# (by default) brings up the API, the interface, and a first search.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CHECK_ONLY=0
ONCE=0
HOST="${SEARCHER_API_HOST:-127.0.0.1}"
PORT="${SEARCHER_API_PORT:-8765}"
WEIGHTS_INSTALL="uv run --extra vision python scripts/prepare_embedding_weights.py"
FIXTURE="$ROOT/fixtures/images/trainer_a.png"
SEARCH_TEXT="Dior Homme General Army Trainer 07"
SEARCH_TAG="footwear"

usage() {
  cat <<'EOF'
Usage: scripts/first_run.sh [--check-only] [--once] [--port N]

  (default)    Report which lanes are live, state the learned backbone,
               start the local API and interface, run a first search,
               print what to do next, and keep the API running.
  --check-only Report lanes and the learned backbone only. Do not start
               the API and do not search.
  --once       After the first search, stop an API this script started
               and exit. Does not stop an API that was already running.
  --port N     Listen port (default 8765, or SEARCHER_API_PORT).
  --help       This message.

This process has no authentication. Only this computer can reach the
default bind (127.0.0.1). Empty Real and Possibly Real lists are an
allowed honest outcome.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --check-only)
      CHECK_ONLY=1
      shift
      ;;
    --once)
      ONCE=1
      shift
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

port_listening() {
  local host="$1" port="$2"
  python3 -c "import socket; s=socket.socket(); s.settimeout(0.3); r=s.connect_ex(('$host', int('$port'))); s.close(); raise SystemExit(0 if r==0 else 1)"
}

require_uv() {
  if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Install it from https://docs.astral.sh/uv/" >&2
    exit 1
  fi
}

require_searcher() {
  if ! uv run python -c "import searcher" >/dev/null 2>&1; then
    echo "Python environment is not ready. From the clone:" >&2
    echo "  uv sync" >&2
    exit 1
  fi
}

print_report() {
  SEARCHER_DATA_ROOT="${SEARCHER_DATA_ROOT:-$ROOT/data}" \
  SEARCHER_LIVE_DISCOVERY="${SEARCHER_LIVE_DISCOVERY:-1}" \
  uv run python - "$WEIGHTS_INSTALL" <<'PY'
import json
import os
import sys
from pathlib import Path

from searcher.campaigns.orchestrator import layers_present
from searcher.core.config import Settings
from searcher.core.embedding_gateway import embedding_capability, find_local_weights
from searcher.integrations.visionmcp.probe import donor_status, probe_capabilities

install = sys.argv[1]
settings = Settings.from_env()
caps = {record.name.value: record for record in probe_capabilities().capabilities}
layers = layers_present()
donor = donor_status()
weights = find_local_weights()
dense = embedding_capability(probe=bool(weights))

data_root = settings.data_root
storage_ok = True
storage_detail = f"Writes under {data_root}."
try:
    data_root.mkdir(parents=True, exist_ok=True)
    probe = data_root / ".first-run-write-probe"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
except OSError as exc:
    storage_ok = False
    storage_detail = f"Cannot write under {data_root}: {exc}"

discovery_live = bool(layers["discovery"] and settings.live_discovery)
if not layers["discovery"]:
    discovery_detail = "The live listing discovery layer is not present in this process."
elif not settings.live_discovery:
    discovery_detail = "Live listing discovery is disabled in this process."
else:
    discovery_detail = "Admitted public sources will be queried."

routing_live = bool(layers["routing"] and settings.live_discovery)
if not layers["routing"]:
    routing_detail = "Sorting into Real and Possibly Real is not present in this process."
elif not settings.live_discovery:
    routing_detail = "Result sorting is disabled in this process."
else:
    routing_detail = "Surviving candidates are sorted into Real and Possibly Real."

if weights is None:
    backbone_detail = (
        "Not present. Matching uses classical descriptors. "
        "Nothing is promoted to Real through a missing-weight fallback."
    )
elif dense.available:
    backbone_detail = f"Present at {weights}. A real probe succeeded."
else:
    backbone_detail = (
        f"A file is present at {weights}, but it is not available. "
        "Availability is a successful probe, not file existence. "
        f"{dense.notes}"
    )

photo = caps.get("IMAGE_DECODE")
ocr = caps.get("OCR")
photo_live = bool(photo and photo.available)
ocr_live = bool(ocr and ocr.available)
donor_live = bool(donor.get("importable"))

lanes = [
    ("Reading photographs", photo_live, "Pillow can decode uploads." if photo_live else "Photograph decode is blocked."),
    ("Live listing discovery", discovery_live, discovery_detail),
    ("Result routing", routing_live, routing_detail),
    ("Learned visual backbone", bool(dense.available), backbone_detail),
    ("Optional visual donor", donor_live, (
        "Vision donor is importable."
        if donor_live
        else "Not installed. Photographs still decode with Pillow. Nothing is promoted to Real through a degraded path. Install with: ./scripts/setup_donor.sh"
    )),
    ("Reading text in photographs", ocr_live, (
        "tesseract is on PATH."
        if ocr_live
        else "tesseract is not on PATH. Searches still run."
    )),
    ("Saving searches on disk", storage_ok, storage_detail),
]

print("Lanes")
print("-----")
width = max(len(name) for name, _live, _detail in lanes)
for name, live, detail in lanes:
    flag = "live" if live else "blocked"
    print(f"  {name:<{width}}  {flag}")
    print(f"    {detail}")

print()
print("Learned visual backbone")
print("-----------------------")
if weights is None:
    print("Status: not present.")
    print("A fresh clone has no model weight files. Searcher never downloads them.")
    print("Matching uses classical descriptors. Nothing is promoted to Real")
    print("through a missing-weight fallback.")
elif dense.available:
    print(f"Status: present ({weights}).")
    print("A real probe succeeded. Classical descriptors still run as well.")
else:
    print(f"Status: not available (file at {weights}).")
    print("Availability is a successful probe, not file existence.")
    print(dense.notes)
print("Install with:")
print(f"  {install}")
print()

report = {
    "lanes": [
        {"name": name, "live": live, "detail": detail} for name, live, detail in lanes
    ],
    "weights_path": str(weights) if weights else None,
    "backbone_available": bool(dense.available),
    "install": install,
}
Path(os.environ.get("SEARCHER_FIRST_RUN_REPORT", "")).write_text(
    json.dumps(report, indent=2) + "\n",
    encoding="utf-8",
) if os.environ.get("SEARCHER_FIRST_RUN_REPORT") else None
PY
}

searcher_health() {
  local base="$1"
  curl -sf --max-time 2 "$base/v1/health" 2>/dev/null || true
}

wait_for_health() {
  local base="$1"
  local _
  for _ in $(seq 1 60); do
    if curl -sf --max-time 2 "$base/v1/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

interface_answers() {
  local base="$1"
  local body
  body="$(curl -sf --max-time 3 "$base/" 2>/dev/null || true)"
  [[ -n "$body" ]]
}

started_api=0
API_PID=""
API_LOG=""

cleanup() {
  if [[ "$started_api" -eq 1 && -n "${API_PID}" ]]; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}

require_uv
require_searcher

echo
echo "Searcher first-run"
echo "------------------"
echo "This process has no authentication. The default bind is this computer only."
echo

print_report

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  echo "Check only. Nothing was started. To bring up the API, the interface,"
  echo "and a first search:"
  echo "  ./scripts/first_run.sh"
  echo
  exit 0
fi

export SEARCHER_API_HOST="$HOST"
export SEARCHER_API_PORT="$PORT"
export SEARCHER_SERVE_WEB="${SEARCHER_SERVE_WEB:-1}"
export SEARCHER_DATA_ROOT="${SEARCHER_DATA_ROOT:-$ROOT/data}"
export SEARCHER_LIVE_DISCOVERY="${SEARCHER_LIVE_DISCOVERY:-1}"

BASE="http://${HOST}:${PORT}"
attach=0

if port_listening "$HOST" "$PORT"; then
  health="$(searcher_health "$BASE")"
  if printf '%s' "$health" | python3 -c 'import json,sys; body=json.load(sys.stdin); raise SystemExit(0 if body.get("api")=="up" else 1)' 2>/dev/null; then
    echo "Port ${PORT} already has Searcher. Attaching."
    attach=1
  else
    echo "address already in use: ${HOST}:${PORT}" >&2
    echo "That port is taken by something that is not Searcher." >&2
    echo "Pick another port:" >&2
    echo "  SEARCHER_API_PORT=8766 ./scripts/first_run.sh" >&2
    exit 1
  fi
fi

if [[ "$attach" -eq 0 ]]; then
  trap cleanup EXIT INT TERM
  API_LOG="$(mktemp -t searcher-first-run.XXXXXX)"
  uv run searcher serve --host "$HOST" --port "$PORT" --static >"$API_LOG" 2>&1 &
  API_PID=$!
  started_api=1
  if ! wait_for_health "$BASE"; then
    echo "API did not become reachable at ${BASE}/v1/health" >&2
    tail -n 40 "$API_LOG" >&2 || true
    exit 1
  fi
  echo "API is up at ${BASE}/"
else
  if ! curl -sf --max-time 2 "$BASE/v1/health" >/dev/null 2>&1; then
    echo "Attached process did not answer ${BASE}/v1/health" >&2
    exit 1
  fi
fi

if ! interface_answers "$BASE"; then
  echo "Interface did not answer at ${BASE}/" >&2
  echo "The API must serve web/ (SEARCHER_SERVE_WEB=1)." >&2
  exit 1
fi
echo "Interface answers at ${BASE}/"

if [[ ! -f "$FIXTURE" ]]; then
  echo "No first-search photograph at $FIXTURE" >&2
  echo "A full clone includes fixtures/images/trainer_a.png." >&2
  exit 1
fi

echo
echo "Starting a first search (one photograph, text, one tag)."
echo "A first live search can take a couple of minutes."
CREATE="$(curl -sf --max-time 30 \
  -F "images=@${FIXTURE};type=image/png" \
  -F "text=${SEARCH_TEXT}" \
  -F "tags=${SEARCH_TAG}" \
  "${BASE}/v1/searches")" || {
  echo "POST ${BASE}/v1/searches failed" >&2
  exit 1
}

SEARCH_ID="$(printf '%s' "$CREATE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["search_id"])')"
echo "search_id: ${SEARCH_ID}"

SEARCH_JSON=""
TERMINAL=""
for _ in $(seq 1 150); do
  SEARCH_JSON="$(curl -sf --max-time 10 "${BASE}/v1/searches/${SEARCH_ID}")" || true
  if [[ -n "$SEARCH_JSON" ]]; then
    TERMINAL="$(printf '%s' "$SEARCH_JSON" | python3 -c 'import json,sys; doc=json.load(sys.stdin); print(doc.get("terminal_status") or "")')"
    if [[ -n "$TERMINAL" ]]; then
      break
    fi
  fi
  sleep 2
done

if [[ -z "$TERMINAL" ]]; then
  echo "First search did not reach a terminal state in time." >&2
  echo "GET ${BASE}/v1/searches/${SEARCH_ID} for the current state." >&2
  exit 1
fi

printf '%s' "$SEARCH_JSON" | python3 -c '
import json, sys
doc = json.load(sys.stdin)
counts = doc.get("counts") or {}
print()
print("First search finished")
print("--------------------")
print("  terminal:", doc.get("terminal_status"))
reason = doc.get("terminal_reason") or ""
if reason:
    print("  reason:  ", reason)
print(
    "  Real: %s  Possibly Real: %s  Hidden: %s"
    % (counts.get("real", 0), counts.get("possibly_real", 0), counts.get("hidden", 0))
)
print("  Empty public lists are allowed. That is not a finding that the item")
print("  does not exist. COMPLETE, PARTIAL, and BLOCKED are all finished.")
'

echo
echo "What to do next"
echo "---------------"
echo "  Open the interface:  ${BASE}/"
echo "  This search:         ${BASE}/  (it is listed there)"
echo "  Health:              ${BASE}/v1/health"
echo "  Share with a friend: ./scripts/serve_shared.sh"
echo "  WARNING: This alpha has no authentication."
echo "  Stop: Ctrl-C. Delete what this process wrote with: rm -rf data"
echo "  Learned backbone (optional): ${WEIGHTS_INSTALL}"
echo

if [[ "$ONCE" -eq 1 ]]; then
  if [[ "$started_api" -eq 1 ]]; then
    echo "Stopping the API this script started (--once)."
    cleanup
    started_api=0
    trap - EXIT INT TERM
  fi
  exit 0
fi

if [[ "$started_api" -eq 1 ]]; then
  echo "API is still running. Ctrl-C stops it."
  wait "$API_PID"
fi
