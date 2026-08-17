#!/usr/bin/env bash
# Bible §32.1: critical-path statement coverage >= 90%, branch >= 80%.
# Measures; does not tune. The areas below are the Searcher-owned critical
# paths - the Bible names the floor but not the paths, so they are named here
# and the choice is visible rather than implied.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

uv run coverage run --branch --source=src/searcher -m pytest -q -p no:randomly "$@"
uv run coverage json -o artifacts/coverage.json --quiet
uv run python - <<'PY'
import json, pathlib
AREAS = ("matching", "ranking", "authenticity", "api", "campaigns", "sources", "retrieval")
d = json.load(open("artifacts/coverage.json"))
rows, failed = [], []
for area in AREAS:
    cs = ns = cb = nb = 0
    for path, info in d["files"].items():
        if f"/searcher/{area}/" in path:
            s = info["summary"]
            cs += s["covered_lines"]; ns += s["num_statements"]
            cb += s.get("covered_branches", 0); nb += s.get("num_branches", 0)
    sp = 100 * cs / ns if ns else 0.0
    bp = 100 * cb / nb if nb else 0.0
    rows.append({"area": area, "statement": round(sp, 1), "branch": round(bp, 1),
                 "meets_floor": sp >= 90 and bp >= 80})
    if not (sp >= 90 and bp >= 80):
        failed.append(area)
t = d["totals"]
out = {
    "floor": {"statement": 90, "branch": 80, "source": "Bible §32.1"},
    "areas": rows,
    "total": {"statement": round(100 * t["covered_lines"] / t["num_statements"], 1),
              "branch": round(100 * t["covered_branches"] / t["num_branches"], 1)},
    "below_floor": failed,
    "note": ("The Bible states the floor but never designates which paths are critical. "
             "The seven areas above are this project's choice, recorded so the number "
             "cannot be moved by quietly renaming what counts."),
}
pathlib.Path("artifacts/searcher-coverage-floor.receipt.json").write_text(json.dumps(out, indent=2) + "\n")
for r in rows:
    mark = "" if r["meets_floor"] else "  <-- below floor"
    print(f"{r['area']:<16}{r['statement']:>6.1f}%{r['branch']:>8.1f}%{mark}")
print(f"\nTOTAL {out['total']['statement']}% statement / {out['total']['branch']}% branch")
print(("FAIL: below floor -> " + ", ".join(failed)) if failed else "PASS: every area meets §32.1")
PY
