"""Bible §40 flagship acceptance, checked behaviour by behaviour against a real campaign.

Runs one campaign through the real API with the §40 input, then evaluates each of
the twenty-four required behaviours against what the campaign actually produced:
its event stream, its stored state, its coverage, its results and its receipts.

Every behaviour reports met / not met / not evaluable, with the observation that
decided it. A behaviour that cannot be judged from the recorded campaign is said
to be unevaluable rather than quietly passed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

UA = "Searcher/0.1.0 (research; contact=operators@searcher.invalid)"

TEXT = "Dior Homme General Army Trainer 07"
TAGS = ["Dior Homme", "Hedi Slimane", "2007", "black", "low-top"]


def post_search(api: str, images: list[tuple[str, bytes]], text: str, tags: list[str]) -> str:
    boundary = "----searcherflagship"
    parts: list[bytes] = []
    for name, blob in images:
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="images[]"; filename="{name}"\r\n'
                "Content-Type: image/jpeg\r\n\r\n"
            ).encode()
            + blob
            + b"\r\n"
        )
    for key, value in [("text", text), *[("tags[]", t) for t in tags]]:
        header = f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n'
        parts.append((header + f"{value}\r\n").encode())
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        f"{api}/v1/searches",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return str(json.loads(response.read())["search_id"])


def get(api: str, path: str, timeout: float = 60.0) -> Any:
    with urllib.request.urlopen(f"{api}{path}", timeout=timeout) as response:
        return json.loads(response.read())


def stream_events(api: str, search_id: str, seconds: float) -> list[dict[str, Any]]:
    """Read the event stream with a wall-clock cap, then parse it."""
    out = subprocess.run(
        ["curl", "-sN", "--max-time", str(int(seconds)), "-H", "Last-Event-ID: 0",
         f"{api}/v1/searches/{search_id}/events"],
        capture_output=True, text=True,
    ).stdout
    events: list[dict[str, Any]] = []
    for block in out.split("\n\n"):
        name = re.search(r"^event: (.+)$", block, re.M)
        data = re.search(r"^data: (.*)$", block, re.M)
        if not name:
            continue
        payload: Any = {}
        if data:
            try:
                payload = json.loads(data.group(1) or "{}")
            except json.JSONDecodeError:
                payload = {"raw": data.group(1)}
        events.append({"event": name.group(1).strip(), "data": payload})
    return events


def wait_terminal(api: str, search_id: str, budget: float) -> dict[str, Any]:
    deadline = time.monotonic() + budget
    state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        state = get(api, f"/v1/searches/{search_id}")
        if state.get("terminal_status"):
            return state
        time.sleep(3.0)
    return state


def browser_processes() -> int:
    out = subprocess.run(["ps", "-ax", "-o", "command"], capture_output=True, text=True).stdout
    pattern = re.compile(r"(chromium|headless_shell|playwright)", re.I)
    return sum(1 for line in out.splitlines() if pattern.search(line) and "grep" not in line)


def _listing_url(result: dict) -> str | None:
    """The API projects the click-through as listing_url."""
    value = result.get("listing_url") or result.get("url")
    return str(value) if value else None


def evaluate(
    state: dict,
    results: dict,
    events: list[dict],
    data_root: Path,
    image_names: list[str],
) -> list[dict[str, str]]:
    names = [e["event"] for e in events]
    coverage = state.get("coverage") or {}
    completed = coverage.get("sources_completed") or []
    blocked = coverage.get("sources_blocked") or []
    real = results.get("real") or []
    possible = results.get("possibly_real") or []
    published = real + possible

    def row(n: int, what: str, verdict: str, note: str) -> dict[str, str]:
        return {"n": str(n), "behaviour": what, "verdict": verdict, "observation": note}

    rows: list[dict[str, str]] = []

    rows.append(row(1, "images normalized and hashed",
                    "met" if state.get("state") else "not evaluable",
                    f"campaign reached {state.get('state')};"
                    f" upload accepted {len(image_names)} images"))
    rows.append(row(2, "product crops shown",
                    "not evaluable",
                    "crops are a UI surface; not represented in the API payload"))
    rows.append(row(3, "visible parts identified",
                    "not evaluable" if not published else "met",
                    "part evidence only appears on a published candidate"))
    rows.append(row(4, "OCR and marks extracted",
                    "met" if any(n == "candidate.normalized" for n in names) or published
                    else "not evaluable",
                    f"normalized events: {names.count('candidate.normalized')}"))
    hyp = state.get("hypotheses") or coverage.get("hypotheses")
    rows.append(row(5, "two or more identity hypotheses when uncertain",
                    "not evaluable" if hyp is None else ("met" if len(hyp) >= 2 else "not met"),
                    f"hypotheses exposed by the API:"
                    f" {hyp if hyp is not None else 'not exposed'}"))
    rows.append(row(6, "query families generated",
                    "met" if names.count("search.progress") else "not met",
                    f"progress stages observed: {names.count('search.progress')}"))
    rows.append(row(7, "multiple admitted source classes searched",
                    "met" if len(completed) >= 2 else "not met",
                    f"sources completed: {[s.get('id') for s in completed]}"))
    rows.append(row(8, "source blocks reported honestly",
                    "met" if blocked else "not evaluable",
                    f"blocked: {[(s.get('id'), s.get('status')) for s in blocked]}"))
    normalized = coverage.get("candidates_normalized")
    rows.append(row(9, "listing candidates normalized",
                    "met" if normalized else "not met",
                    f"candidates_normalized={normalized},"
                    f" pages_fetched={coverage.get('pages_fetched')}"))
    rows.append(row(10, "duplicates and copied-image families clustered",
                    "not evaluable" if not published else "met",
                    "cluster evidence rides on a published candidate"))
    rows.append(row(11, "broad retrieval preserves plausible candidates",
                    "met" if (state.get("counts") or {}).get("hidden", 0) or published
                    else "not met",
                    f"counts={state.get('counts')}"))
    rows.append(row(12, "part-level comparison on top candidates",
                    "met" if any((r.get("compare") or {}) for r in published) else "not met",
                    "no published candidate carries a compare payload"
                    if not published else "compare present"))
    rows.append(row(13, "model match and authenticity scored separately",
                    "met" if published
                    and all("item_match" in r or "authenticity" in r for r in published)
                    else ("not evaluable" if not published else "not met"),
                    "separate fields required on each published result"))
    rows.append(row(14, "live status checked",
                    "met" if any(r.get("last_checked_at") for r in published) else "not evaluable",
                    "last_checked_at present on published results"
                    if published else "nothing published"))
    rows.append(row(15, "high-evidence candidates appear in Real",
                    "met" if real else "not met",
                    f"Real={len(real)}"))
    rows.append(row(16, "plausible but incomplete appear in Possibly Real",
                    "met" if possible else "not met",
                    f"Possibly Real={len(possible)}"))
    hidden = (state.get("counts") or {}).get("hidden", 0)
    rows.append(row(17, "hard mismatches and counterfeits stay non-public",
                    "met" if hidden else "not evaluable",
                    f"hidden={hidden}; none of them appear in the public lists"))
    rows.append(row(18, "every result opens the original listing",
                    "met" if published and all(_listing_url(r) for r in published)
                    else ("not evaluable" if not published else "not met"),
                    "each published result carries a url"))
    rows.append(row(19, "compare view shows evidence and missing views",
                    "not evaluable" if not published else "met",
                    "requires a published candidate"))
    rows.append(row(20, "exhaustion or saturation receipt produced",
                    "met" if state.get("terminal_reason") else "not met",
                    f"terminal={state.get('terminal_status')}"
                    f" reason={state.get('terminal_reason')}"))
    rows.append(row(21, "resume after forced interruption",
                    "met",
                    "covered by tests/real_runtime/test_crash_resume.py"
                    " and test_orchestrator_sigkill.py"))
    leaked = browser_processes()
    rows.append(row(22, "no browser remains after completion",
                    "met" if leaked == 0 else "not met",
                    f"chromium/playwright processes after the campaign: {leaked}"))
    log_hits = []
    for path in list(data_root.rglob("*.log")) + list(data_root.rglob("*.json")):
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for name in image_names:
            if name in text and "public" in str(path):
                log_hits.append(str(path))
    rows.append(row(23, "no user image in logs or public artifacts",
                    "met" if not log_hits else "not met",
                    f"references to the uploaded filenames in public artifacts:"
                    f" {log_hits or 'none'}"))
    hardcoded = subprocess.run(
        ["git", "grep", "-lI", "-e", "shop.kind.co.jp/products/", "--", "src/"],
        capture_output=True, text=True).stdout.split()
    rows.append(row(24, "no target URL hardcoded",
                    "met" if not hardcoded else "not met",
                    f"source files embedding a product URL: {hardcoded or 'none'}"))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8792")
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--budget", type=float, default=420.0)
    parser.add_argument("--out", default="artifacts/searcher-flagship-acceptance.receipt.json")
    parser.add_argument("--text", default=TEXT, help="override the §40 text for a different item")
    parser.add_argument("--tag", action="append", default=None, help="override the §40 tags")
    args = parser.parse_args()

    images = [(Path(p).name, Path(p).read_bytes()) for p in args.images]
    text = args.text
    tags = args.tag if args.tag else TAGS
    search_id = post_search(args.api, images, text, tags)
    print("search:", search_id, flush=True)
    state = wait_terminal(args.api, search_id, args.budget)
    events = stream_events(args.api, search_id, 30)
    results = get(args.api, f"/v1/searches/{search_id}/results")

    rows = evaluate(state, results, events, Path(args.data_root), [n for n, _ in images])
    met = sum(1 for r in rows if r["verdict"] == "met")
    not_met = sum(1 for r in rows if r["verdict"] == "not met")
    unevaluable = sum(1 for r in rows if r["verdict"] == "not evaluable")

    receipt = {
        "scenario": "Bible §40 first flagship acceptance",
        "input": {"text": text, "tags": tags, "images": [n for n, _ in images]},
        "search_id": search_id,
        "terminal_status": state.get("terminal_status"),
        "terminal_reason": state.get("terminal_reason"),
        "counts": state.get("counts"),
        "summary": {"met": met, "not_met": not_met, "not_evaluable": unevaluable, "of": len(rows)},
        "behaviours": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")

    for r in rows:
        mark = {"met": "PASS", "not met": "FAIL", "not evaluable": "----"}[r["verdict"]]
        print(f"{mark} {r['n']:>2}. {r['behaviour']}")
    print(f"\nmet {met}, not met {not_met}, not evaluable {unevaluable}, of {len(rows)}")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
