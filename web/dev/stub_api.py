#!/usr/bin/env python3
"""
DEVELOPMENT ONLY.

This process is not part of the Searcher product and must never be deployed
with the GitHub Pages site. It implements a scripted subset of the §26.2 API
so the static interface can be developed and demonstrated before the real
engine exists.

Python 3 standard library only. No third-party packages.
"""

from __future__ import annotations

import argparse
import copy
import json
import mimetypes
import posixpath
import sys
import threading
import time
import uuid
from email import message_from_bytes
from email.policy import default as email_default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
WEB_ROOT = HERE.parent
FIXTURES = HERE / "fixtures"
RESULTS_DIR = FIXTURES / "results"
SEARCHES_DIR = FIXTURES / "searches"
EVENTS_DIR = FIXTURES / "events"

HOST = "127.0.0.1"
DEFAULT_PORT = 8765

SCENARIO_FILES = {
    "normal": "normal",
    "empty-real": "empty-real",
    "empty": "empty",
    "cancelled": "cancelled",
    "failed": "failed",
    "blocked": "blocked",
    "partial": "partial",
    "xss": "xss",
}

SEEDED_IDS = {
    "fixture-normal": "normal",
    "fixture-empty-real": "empty-real",
    "fixture-empty": "empty",
    "fixture-cancelled": "cancelled",
    "fixture-failed": "failed",
    "fixture-blocked": "blocked",
    "fixture-partial": "partial",
    "fixture-xss": "xss",
}

LOCK = threading.RLock()
CAMPAIGNS: dict[str, dict[str, Any]] = {}
RESULT_INDEX: dict[str, dict[str, Any]] = {}
CLIENT_INDEX: dict[str, str] = {}


def log(msg: str) -> None:
    print(f"[stub] {msg}", file=sys.stderr, flush=True)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_result(result_id: str) -> dict[str, Any]:
    path = RESULTS_DIR / f"{result_id}.json"
    if not path.is_file():
        raise FileNotFoundError(result_id)
    return load_json(path)


def detect_scenario(text: str, tags: list[str]) -> str:
    blob = " ".join([text, *tags]).lower()
    checks = (
        ("empty-real", "empty-real"),
        ("empty real", "empty-real"),
        ("no candidates", "empty"),
        ("empty-all", "empty"),
        ("xss", "xss"),
        ("blocked", "blocked"),
        ("partial", "partial"),
        ("cancel", "cancelled"),
        ("error", "failed"),
        ("fail", "failed"),
    )
    for needle, name in checks:
        if needle in blob:
            return name
    tokens = {t.strip().lower() for t in tags}
    if "empty" in tokens:
        return "empty"
    return "normal"


def clone_result(src: dict[str, Any], search_id: str) -> dict[str, Any]:
    obj = copy.deepcopy(src)
    original = obj["result_id"]
    obj["result_id"] = f"{search_id[:8]}-{original}"
    obj["search_id"] = search_id
    obj["_source_result_id"] = original
    return obj


def empty_coverage() -> dict[str, Any]:
    return {
        "sources_completed": [],
        "sources_blocked": [],
        "sources_in_progress": [],
        "pages_fetched": 0,
        "candidates_normalized": 0,
        "candidates_hidden": 0,
    }


def prepare_campaign(
    search_id: str,
    scenario: str,
    text: str,
    tags: list[str],
    *,
    seed: bool = False,
    client_search_id: str | None = None,
) -> dict[str, Any]:
    template = load_json(SEARCHES_DIR / f"fixture-{scenario if scenario != 'empty-real' else 'empty-real'}.json")
    events_spec = load_json(EVENTS_DIR / f"{scenario}.json")

    result_map: dict[str, dict[str, Any]] = {}
    public = {"real": [], "possibly_real": []}
    for bucket, ids in template.get("result_ids", {}).items():
        for rid in ids:
            if seed:
                obj = copy.deepcopy(load_result(rid))
                obj["search_id"] = search_id
                result_map[rid] = obj
                public[bucket].append(rid)
            else:
                cloned = clone_result(load_result(rid), search_id)
                result_map[cloned["result_id"]] = cloned
                result_map[rid] = cloned

    # Results that appear only in the event stream (then maybe removed).
    extra_ids = set()
    for spec in events_spec:
        data = spec.get("data") or {}
        if spec.get("event") in {"result.real", "result.possibly_real", "result.removed"}:
            extra_ids.add(data.get("result_id"))
    for rid in extra_ids:
        if rid and rid not in result_map:
            try:
                cloned = clone_result(load_result(rid), search_id)
            except FileNotFoundError:
                continue
            result_map[cloned["result_id"]] = cloned
            result_map[rid] = cloned

    events: list[dict[str, Any]] = []
    for i, spec in enumerate(events_spec, start=1):
        data = copy.deepcopy(spec.get("data") or {})
        event_name = spec["event"]
        if event_name in {"result.real", "result.possibly_real", "result.removed"}:
            src_id = data.get("result_id")
            cloned = result_map.get(src_id)
            if cloned is None:
                continue
            if event_name == "result.removed":
                data = {"result_id": cloned["result_id"], "reason": data.get("reason") or "hidden"}
            else:
                data = freshen_result(cloned)
        events.append(
            {
                "id": i,
                "event": event_name,
                "data": data,
                "delay_ms": int(spec.get("delay_ms") or 0),
            }
        )

    if seed:
        state = template["state"]
        terminal = template.get("terminal_status")
        progress = copy.deepcopy(template.get("progress") or {})
        coverage = copy.deepcopy(template.get("coverage") or empty_coverage())
        counts = copy.deepcopy(template.get("counts") or {"real": 0, "possibly_real": 0, "hidden": 0})
        hidden_note = template.get("hidden_policy_note")
        missing_views = copy.deepcopy(template.get("missing_reference_views") or [])
        deeper = bool(template.get("deeper_refresh_available"))
        done = True
        emitted = list(events)
    else:
        state = "CREATED"
        terminal = None
        progress = {"stage": None, "detail": None}
        coverage = empty_coverage()
        counts = {"real": 0, "possibly_real": 0, "hidden": 0}
        hidden_note = None
        missing_views = []
        deeper = False
        public = {"real": [], "possibly_real": []}
        done = False
        emitted = []

    camp = {
        "search_id": search_id,
        "scenario": scenario,
        "state": state,
        "state_version": template.get("state_version") or 1,
        "terminal_status": terminal,
        "terminal_reason": template.get("terminal_reason") if seed else None,
        "created_at": template.get("created_at"),
        "updated_at": template.get("updated_at"),
        "progress": progress,
        "coverage": coverage,
        "counts": counts,
        "hidden_policy_note": hidden_note,
        "missing_reference_views": missing_views,
        "deeper_refresh_available": deeper,
        "_template_hidden_note": template.get("hidden_policy_note"),
        "_template_missing_views": copy.deepcopy(template.get("missing_reference_views") or []),
        "_template_deeper": bool(template.get("deeper_refresh_available")),
        "_template_coverage": copy.deepcopy(template.get("coverage") or empty_coverage()),
        "intent": {"text": text, "tags": list(tags)},
        "events_url": f"/v1/searches/{search_id}/events",
        "results_url": f"/v1/searches/{search_id}/results",
        "result_ids": public,
        "result_map": result_map,
        "events": events,
        "emitted": emitted,
        "done": done,
        "cancelled": seed and terminal == "CANCELLED",
        "deleted": False,
        "client_search_id": client_search_id,
        "cond": threading.Condition(),
    }
    return camp


def register_campaign(camp: dict[str, Any]) -> None:
    with LOCK:
        CAMPAIGNS[camp["search_id"]] = camp
        if camp.get("client_search_id"):
            CLIENT_INDEX[camp["client_search_id"]] = camp["search_id"]
        for rid, obj in camp["result_map"].items():
            if rid == obj["result_id"]:
                RESULT_INDEX[rid] = obj


def recent_iso(seconds_ago: int = 90) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds_ago))


def freshen_result(obj: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(obj)
    checked = recent_iso(90)
    out["last_checked_at"] = checked
    if isinstance(out.get("listing_utility"), dict):
        out["listing_utility"]["last_checked_at"] = checked
    if isinstance(out.get("why"), dict):
        out["why"]["checked_at"] = checked
    return out


def public_search(camp: dict[str, Any]) -> dict[str, Any]:
    return {
        "search_id": camp["search_id"],
        "state": camp["state"],
        "state_version": camp["state_version"],
        "terminal_status": camp["terminal_status"],
        "terminal_reason": camp["terminal_reason"],
        "created_at": camp["created_at"],
        "updated_at": camp["updated_at"],
        "progress": camp["progress"],
        "coverage": camp["coverage"],
        "counts": camp["counts"],
        "hidden_policy_note": camp["hidden_policy_note"],
        "missing_reference_views": camp["missing_reference_views"],
        "deeper_refresh_available": camp["deeper_refresh_available"],
        "intent": camp["intent"],
        "events_url": camp["events_url"],
        "results_url": camp["results_url"],
    }


def results_payload(camp: dict[str, Any], bucket: str | None) -> dict[str, Any]:
    def collect(name: str) -> list[dict[str, Any]]:
        out = []
        for rid in camp["result_ids"].get(name, []):
            obj = camp["result_map"].get(rid)
            if obj:
                out.append(freshen_result(obj))
        return out

    if bucket == "real":
        return {"search_id": camp["search_id"], "bucket": "real", "results": collect("real")}
    if bucket == "possibly_real":
        return {
            "search_id": camp["search_id"],
            "bucket": "possibly_real",
            "results": collect("possibly_real"),
        }
    return {
        "search_id": camp["search_id"],
        "real": collect("real"),
        "possibly_real": collect("possibly_real"),
        "counts": camp["counts"],
    }


def apply_event(camp: dict[str, Any], event: str, data: dict[str, Any]) -> None:
    if event == "search.state":
        camp["state"] = data.get("state") or camp["state"]
        camp["state_version"] = data.get("version") or camp["state_version"]
    elif event == "search.progress":
        camp["progress"] = {
            "stage": data.get("stage"),
            "detail": data.get("detail"),
        }
    elif event == "search.coverage":
        camp["coverage"] = copy.deepcopy(data)
    elif event in {"result.real", "result.possibly_real"}:
        rid = data["result_id"]
        camp["result_map"][rid] = data
        RESULT_INDEX[rid] = data
        other = "possibly_real" if event == "result.real" else "real"
        if rid in camp["result_ids"][other]:
            camp["result_ids"][other].remove(rid)
        bucket = "real" if event == "result.real" else "possibly_real"
        if rid not in camp["result_ids"][bucket]:
            camp["result_ids"][bucket].append(rid)
        camp["counts"]["real"] = len(camp["result_ids"]["real"])
        camp["counts"]["possibly_real"] = len(camp["result_ids"]["possibly_real"])
    elif event == "result.removed":
        rid = data.get("result_id")
        for bucket in ("real", "possibly_real"):
            if rid in camp["result_ids"][bucket]:
                camp["result_ids"][bucket].remove(rid)
        camp["counts"]["real"] = len(camp["result_ids"]["real"])
        camp["counts"]["possibly_real"] = len(camp["result_ids"]["possibly_real"])
        camp["counts"]["hidden"] = int(camp["counts"].get("hidden") or 0) + 1
        if not camp.get("hidden_policy_note"):
            camp["hidden_policy_note"] = "Some candidates did not meet policy."
    elif event == "search.complete":
        camp["terminal_status"] = data.get("terminal_status")
        camp["terminal_reason"] = data.get("reason")
        camp["state"] = data.get("terminal_status") or camp["state"]
        camp["done"] = True
        if not camp.get("hidden_policy_note"):
            camp["hidden_policy_note"] = camp.get("_template_hidden_note")
        if not camp.get("missing_reference_views"):
            camp["missing_reference_views"] = copy.deepcopy(camp.get("_template_missing_views") or [])
        camp["deeper_refresh_available"] = camp.get("_template_deeper")
        if not camp.get("coverage") or not camp["coverage"].get("sources_completed"):
            if camp.get("_template_coverage"):
                camp["coverage"] = copy.deepcopy(camp["_template_coverage"])


def run_stream(search_id: str) -> None:
    with LOCK:
        camp = CAMPAIGNS.get(search_id)
        if camp is None:
            return
        pending = [e for e in camp["events"] if e not in camp["emitted"]]
    for spec in pending:
        delay = max(0, int(spec.get("delay_ms") or 0)) / 1000.0
        if delay:
            time.sleep(delay)
        with LOCK:
            camp = CAMPAIGNS.get(search_id)
            if camp is None or camp.get("deleted"):
                return
            if camp.get("cancelled"):
                closing = {
                    "id": (camp["emitted"][-1]["id"] + 1) if camp["emitted"] else 1,
                    "event": "search.complete",
                    "data": {
                        "terminal_status": "CANCELLED",
                        "reason": "The search was cancelled before the campaign finished.",
                    },
                    "delay_ms": 0,
                }
                apply_event(camp, closing["event"], closing["data"])
                camp["emitted"].append(closing)
                camp["done"] = True
                with camp["cond"]:
                    camp["cond"].notify_all()
                return
            apply_event(camp, spec["event"], spec["data"])
            camp["emitted"].append(spec)
            if spec["event"] == "search.complete":
                camp["done"] = True
            with camp["cond"]:
                camp["cond"].notify_all()


def ensure_seeded(search_id: str) -> dict[str, Any] | None:
    with LOCK:
        if search_id in CAMPAIGNS:
            camp = CAMPAIGNS[search_id]
            return None if camp.get("deleted") else camp
        scenario = SEEDED_IDS.get(search_id)
        if not scenario:
            return None
        template = load_json(SEARCHES_DIR / f"fixture-{scenario}.json")
        intent = template.get("intent") or {"text": "", "tags": []}
        camp = prepare_campaign(
            search_id,
            scenario,
            intent.get("text") or "",
            list(intent.get("tags") or []),
            seed=True,
        )
        register_campaign(camp)
        return camp


def parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, list[str]], list[tuple[str, str, str, bytes]]]:
    header = b"MIME-Version: 1.0\r\nContent-Type: " + content_type.encode("latin-1") + b"\r\n\r\n"
    msg = message_from_bytes(header + body, policy=email_default)
    fields: dict[str, list[str]] = {}
    files: list[tuple[str, str, str, bytes]] = []
    if not msg.is_multipart():
        return fields, files
    for part in msg.iter_parts():
        disp = part.get("Content-Disposition", "")
        if "form-data" not in disp:
            continue
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True)
        if payload is None:
            payload = b""
        if not name:
            continue
        if filename:
            ctype = part.get_content_type() or "application/octet-stream"
            files.append((str(name), str(filename), ctype, payload))
        else:
            fields.setdefault(str(name), []).append(payload.decode("utf-8", errors="replace"))
    return fields, files


def first_field(fields: dict[str, list[str]], *names: str) -> str:
    for name in names:
        values = fields.get(name)
        if values:
            return values[0]
        values = fields.get(f"{name}[]")
        if values:
            return values[0]
    return ""


def all_fields(fields: dict[str, list[str]], *names: str) -> list[str]:
    out: list[str] = []
    for name in names:
        out.extend(fields.get(name) or [])
        out.extend(fields.get(f"{name}[]") or [])
    return [v.strip() for v in out if v and v.strip()]


def safe_under(root: Path, rel: str) -> Path | None:
    rel = rel.lstrip("/")
    if not rel or ".." in posixpath.normpath(rel).split("/"):
        return None
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


class Handler(BaseHTTPRequestHandler):
    server_version = "SearcherStub/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        log(f"{self.address_string()} {fmt % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Last-Event-ID")
        self.send_header("Access-Control-Expose-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path in {"/v1/health", "/health"}:
            return self._send_json(HTTPStatus.OK, load_json(FIXTURES / "health.json"))
        if path == "/v1/capabilities":
            return self._send_json(HTTPStatus.OK, load_json(FIXTURES / "capabilities.json"))

        if path.startswith("/v1/searches/") and path.endswith("/events"):
            search_id = path[len("/v1/searches/") : -len("/events")]
            return self._sse(search_id)
        if path.startswith("/v1/searches/") and path.endswith("/results"):
            search_id = path[len("/v1/searches/") : -len("/results")]
            bucket = (query.get("bucket") or [None])[0]
            return self._results(search_id, bucket)
        if path.startswith("/v1/searches/") and path.count("/") == 3:
            search_id = path.rsplit("/", 1)[-1]
            return self._search(search_id)
        if path.startswith("/v1/results/") and path.count("/") == 3:
            result_id = path.rsplit("/", 1)[-1]
            return self._result(result_id)

        if path.startswith("/v1/"):
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})

        return self._static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        if path == "/v1/searches":
            return self._create(body)
        if path.startswith("/v1/searches/") and path.endswith("/cancel"):
            search_id = path[len("/v1/searches/") : -len("/cancel")]
            return self._cancel(search_id)
        if path.startswith("/v1/searches/") and path.endswith("/refresh"):
            search_id = path[len("/v1/searches/") : -len("/refresh")]
            camp = ensure_seeded(search_id)
            if camp is None:
                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "search_not_found"})
            return self._send_json(HTTPStatus.ACCEPTED, public_search(camp))
        if path.startswith("/v1/results/") and path.endswith("/feedback"):
            return self._send_json(HTTPStatus.ACCEPTED, {"ok": True})
        return self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path.startswith("/v1/searches/") and path.count("/") == 3:
            search_id = path.rsplit("/", 1)[-1]
            return self._delete(search_id)
        return self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})

    def _create(self, body: bytes) -> None:
        content_type = self.headers.get("Content-Type") or ""
        text = ""
        tags: list[str] = []
        client_search_id = ""
        n_images = 0
        if content_type.lower().startswith("multipart/form-data"):
            fields, files = parse_multipart(content_type, body)
            text = first_field(fields, "text")
            tags = all_fields(fields, "tags")
            client_search_id = first_field(fields, "client_search_id")
            image_files = [f for f in files if f[0] in {"images", "images[]", "image"}]
            n_images = len(image_files)
        elif content_type.lower().startswith("application/json") and body:
            payload = json.loads(body.decode("utf-8"))
            text = str(payload.get("text") or "")
            tags = [str(t) for t in (payload.get("tags") or [])]
            client_search_id = str(payload.get("client_search_id") or "")
            n_images = int(payload.get("image_count") or 0)
        else:
            return self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"error": "expected_multipart", "detail": "POST /v1/searches expects multipart/form-data."},
            )

        if n_images < 1:
            return self._send_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {
                    "error": "validation",
                    "detail": "A search needs at least one image. The server is the validator.",
                },
            )
        if n_images > 10:
            return self._send_json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {
                    "error": "validation",
                    "detail": "A search can include at most 10 images. The server is the validator.",
                },
            )

        if client_search_id:
            with LOCK:
                existing_id = CLIENT_INDEX.get(client_search_id)
                if existing_id and existing_id in CAMPAIGNS and not CAMPAIGNS[existing_id].get("deleted"):
                    camp = CAMPAIGNS[existing_id]
                    return self._send_json(HTTPStatus.OK, public_search(camp))

        scenario = detect_scenario(text, tags)
        search_id = str(uuid.uuid4())
        camp = prepare_campaign(search_id, scenario, text, tags, client_search_id=client_search_id or None)
        register_campaign(camp)
        threading.Thread(target=run_stream, args=(search_id,), name=f"stream-{search_id[:8]}", daemon=True).start()
        return self._send_json(HTTPStatus.CREATED, public_search(camp))

    def _search(self, search_id: str) -> None:
        camp = ensure_seeded(search_id)
        if camp is None:
            return self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "search_not_found", "detail": "This search is no longer available."},
            )
        return self._send_json(HTTPStatus.OK, public_search(camp))

    def _results(self, search_id: str, bucket: str | None) -> None:
        camp = ensure_seeded(search_id)
        if camp is None:
            return self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "search_not_found", "detail": "This search is no longer available."},
            )
        if bucket and bucket not in {"real", "possibly_real"}:
            return self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "bad_bucket", "detail": "bucket must be real or possibly_real."},
            )
        return self._send_json(HTTPStatus.OK, results_payload(camp, bucket))

    def _result(self, result_id: str) -> None:
        with LOCK:
            obj = RESULT_INDEX.get(result_id)
            if obj is None:
                try:
                    obj = load_result(result_id)
                except FileNotFoundError:
                    obj = None
        if obj is None:
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "result_not_found"})
        return self._send_json(HTTPStatus.OK, freshen_result(obj))

    def _cancel(self, search_id: str) -> None:
        camp = ensure_seeded(search_id)
        if camp is None:
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "search_not_found"})
        with LOCK:
            camp["cancelled"] = True
            if not camp["done"]:
                camp["state"] = "CANCELLED"
                camp["terminal_status"] = "CANCELLED"
                camp["terminal_reason"] = "The search was cancelled before the campaign finished."
            with camp["cond"]:
                camp["cond"].notify_all()
        return self._send_json(HTTPStatus.OK, public_search(camp))

    def _delete(self, search_id: str) -> None:
        camp = ensure_seeded(search_id)
        if camp is None:
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "search_not_found"})
        with LOCK:
            camp["deleted"] = True
            camp["done"] = True
            camp["cancelled"] = True
            with camp["cond"]:
                camp["cond"].notify_all()
            for rid, obj in list(camp["result_map"].items()):
                if RESULT_INDEX.get(rid) is obj:
                    RESULT_INDEX.pop(rid, None)
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.end_headers()
        return

    def _sse(self, search_id: str) -> None:
        camp = ensure_seeded(search_id)
        if camp is None:
            return self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": "search_not_found", "detail": "This search is no longer available."},
            )
        last_raw = self.headers.get("Last-Event-ID") or "0"
        try:
            last_id = int(last_raw)
        except ValueError:
            last_id = 0

        self.send_response(HTTPStatus.OK)
        self._cors()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                with camp["cond"]:
                    batch = [e for e in camp["emitted"] if e["id"] > last_id]
                    if not batch and camp["done"]:
                        break
                    if not batch:
                        camp["cond"].wait(timeout=0.5)
                        continue
                for event in batch:
                    payload = (
                        f"id: {event['id']}\n"
                        f"event: {event['event']}\n"
                        f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                    )
                    self.wfile.write(payload.encode("utf-8"))
                    self.wfile.flush()
                    last_id = event["id"]
                if camp["done"] and last_id >= (camp["emitted"][-1]["id"] if camp["emitted"] else 0):
                    break
        except BrokenPipeError:
            return
        except ConnectionResetError:
            return

    def _static(self, path: str) -> None:
        if path in {"/search", "/privacy", "/limitations"} or path.startswith("/search/"):
            loc = "/#" + (path if path != "/" else "/")
            self.send_response(HTTPStatus.FOUND)
            self._cors()
            self.send_header("Location", loc)
            self.end_headers()
            return

        rel = path.lstrip("/")
        if not rel:
            rel = "index.html"
        if rel.startswith("dev/fixtures/images/"):
            target = safe_under(FIXTURES, rel[len("dev/fixtures/") :])
        else:
            target = safe_under(WEB_ROOT, rel)
            if target and target.is_dir():
                target = target / "index.html"
        if target is None or not target.is_file():
            # SPA-style fallback for refresh of pretty paths.
            if path.startswith("/search/") or path in {"/privacy", "/limitations"}:
                target = WEB_ROOT / "index.html"
            else:
                return self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})

        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix == ".js":
            ctype = "text/javascript; charset=utf-8"
        elif target.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif target.suffix == ".svg":
            ctype = "image/svg+xml"
        elif target.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, code: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Development-only Searcher API stub.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    log("DEVELOPMENT ONLY — not part of the deployed site.")
    log(f"UI + API at http://{args.host}:{args.port}/")
    log(f"Split UI: python3 -m http.server 8080 --directory {WEB_ROOT}")
    log(f"           then open http://127.0.0.1:8080/?api=http://{args.host}:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
