#!/usr/bin/env bash
# Live known-item check: photos from KIND listing 8001001141404 must come back
# in Real or Possibly Real, ranked first when present.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST="${SEARCHER_API_HOST:-127.0.0.1}"
# Dedicated port so we never attach to an unrelated searcher on 8765.
PORT="${SEARCHER_API_PORT:-8788}"
BASE="http://${HOST}:${PORT}"
DATA_ROOT="${SEARCHER_DATA_ROOT:-/tmp/searcher-realmatch-livecheck}"
WEIGHTS="${SEARCHER_EMBEDDING_WEIGHTS:-/tmp/searcher-realmatch-data/models/embedding.pt}"
OUT="$ROOT/artifacts/realmatch"
mkdir -p "$OUT"

if [[ ! -f "$WEIGHTS" ]]; then
  echo "preparing embedding weights at $WEIGHTS"
  mkdir -p "$(dirname "$WEIGHTS")"
  SEARCHER_DATA_ROOT="$(dirname "$(dirname "$WEIGHTS")")" \
    uv run --extra vision python "$ROOT/scripts/prepare_embedding_weights.py" --output "$WEIGHTS"
fi

if [[ ! -d "$ROOT/fixtures/known_item_kind/images" ]]; then
  uv run python "$ROOT/scripts/fetch_known_item_fixtures.py"
fi

export SEARCHER_DATA_ROOT="$DATA_ROOT"
export SEARCHER_EMBEDDING_WEIGHTS="$WEIGHTS"
export SEARCHER_EMBEDDING_DEVICE="${SEARCHER_EMBEDDING_DEVICE:-cpu}"
export SEARCHER_LIVE_DISCOVERY="${SEARCHER_LIVE_DISCOVERY:-1}"
export SEARCHER_SERVE_WEB="${SEARCHER_SERVE_WEB:-0}"
export SEARCHER_API_HOST="$HOST"
export SEARCHER_API_PORT="$PORT"

started_server=0
if curl --max-time 2 -sS "$BASE/v1/health" >/dev/null 2>&1; then
  echo "attaching to existing server at $BASE"
else
  if [[ -f "$OUT/server.pid" ]]; then
    old_pid="$(cat "$OUT/server.pid" || true)"
    if [[ -n "${old_pid}" ]] && kill -0 "$old_pid" >/dev/null 2>&1; then
      kill "$old_pid" >/dev/null 2>&1 || true
      sleep 1
    fi
    rm -f "$OUT/server.pid"
  fi
  mkdir -p "$DATA_ROOT"
  uv run --extra vision searcher serve \
    --host "$HOST" --port "$PORT" --data-root "$DATA_ROOT" --no-static \
    >"$OUT/server.log" 2>&1 &
  echo $! >"$OUT/server.pid"
  started_server=1
  up=0
  for _ in $(seq 1 60); do
    if curl --max-time 2 -sS "$BASE/v1/health" >/dev/null 2>&1; then
      up=1
      break
    fi
    sleep 0.5
  done
  if [[ "$up" -ne 1 ]]; then
    echo "server failed to start on $BASE" >&2
    tail -n 40 "$OUT/server.log" >&2 || true
    exit 1
  fi
fi

IMGS=()
for f in "$ROOT/fixtures/known_item_kind/images/8001001141404_1.jpg" \
         "$ROOT/fixtures/known_item_kind/images/8001001141404_2.jpg" \
         "$ROOT/fixtures/known_item_kind/images/8001001141404_3.jpg"; do
  if [[ -f "$f" ]]; then
    IMGS+=(-F "images=@${f}")
  fi
done
if [[ ${#IMGS[@]} -eq 0 ]]; then
  echo "no cached listing photos; run scripts/fetch_known_item_fixtures.py" >&2
  exit 1
fi

CREATE="$(curl --max-time 30 -sS -X POST "$BASE/v1/searches" \
  "${IMGS[@]}" \
  -F "text=Willy Chavarria black long sleeve" \
  -F "tags=Willy Chavarria" \
  -F "tags=shirt")"
echo "$CREATE" | tee "$OUT/create.json"
SEARCH_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["search_id"])' <<<"$CREATE")"
echo "search_id=$SEARCH_ID"

curl --max-time 360 -sS -N "$BASE/v1/searches/${SEARCH_ID}/events" | tee "$OUT/sse.txt" >/dev/null &
SSE_PID=$!
# Poll until terminal or ~5 minutes. Live discovery plus matching needs wall room.
for _ in $(seq 1 150); do
  STATUS="$(curl --max-time 10 -sS "$BASE/v1/searches/${SEARCH_ID}")"
  echo "$STATUS" >"$OUT/search.json"
  python3 - <<'PY' "$OUT/search.json" && break || true
import json, sys
doc = json.loads(open(sys.argv[1]).read())
state = doc.get("state") or ""
term = doc.get("terminal_status")
print(state, term)
sys.exit(0 if term or state in {"COMPLETE", "PARTIAL", "BLOCKED", "FAILED"} else 1)
PY
  sleep 2
done
kill "$SSE_PID" >/dev/null 2>&1 || true
wait "$SSE_PID" >/dev/null 2>&1 || true

curl --max-time 20 -sS "$BASE/v1/searches/${SEARCH_ID}/results" | tee "$OUT/results.json" >/dev/null
python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/realmatch")
results = json.loads((out / "results.json").read_text())
search = json.loads((out / "search.json").read_text())
target = "8001001141404"
real = results.get("real") or []
possible = results.get("possibly_real") or []
def rank_of(rows):
    for i, row in enumerate(rows, 1):
        url = row.get("listing_url") or ""
        if target in url:
            return i, row
    return None, None
rr, rrow = rank_of(real)
pr, prow = rank_of(possible)
row = rrow or prow or {}
report = {
    "search_id": search.get("search_id"),
    "terminal_status": search.get("terminal_status") or search.get("state"),
    "terminal_reason": search.get("terminal_reason"),
    "counts": search.get("counts") or results.get("counts"),
    "coverage": search.get("coverage"),
    "target_in_real_rank": rr,
    "target_in_possibly_real_rank": pr,
    "target_url_real": (rrow or {}).get("listing_url"),
    "target_url_possible": (prow or {}).get("listing_url"),
    "why": row.get("why"),
    "item_match": row.get("item_match"),
    "reason": row.get("reason") or row.get("reason_codes"),
}
(out / "known_item_summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(report, indent=2, ensure_ascii=False))
if rr is None and pr is None:
    print("SOURCE LISTING NOT IN PUBLIC TABS", flush=True)
    raise SystemExit(2)
PY

if [[ "$started_server" -eq 1 && -f "$OUT/server.pid" ]]; then
  kill "$(cat "$OUT/server.pid")" >/dev/null 2>&1 || true
fi
echo "artifacts written under $OUT"
