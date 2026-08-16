"""Measure cold and warm latency on this host. Do not tune to the target."""

from __future__ import annotations

import argparse
import io
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image

from searcher.api.main import create_app
from searcher.bench.receipt import write_receipt
from searcher.campaigns.controller import CampaignController
from searcher.campaigns.runner import FixtureRunner
from searcher.core.config import Settings
from searcher.evidence.content_store import ContentStore
from searcher.reference.imaging import open_rgb
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate


def _png(color: tuple[int, int, int] = (20, 40, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(buf, format="PNG")
    return buf.getvalue()


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)


def _client(data_root: Path) -> TestClient:
    os.environ["SEARCHER_DATA_ROOT"] = str(data_root)
    os.environ["SEARCHER_SERVE_WEB"] = "1"
    settings = Settings.from_env(data_root=data_root)
    return TestClient(create_app(settings))


def _measure_http(client: TestClient) -> dict[str, Any]:
    out: dict[str, Any] = {
        "transport": "asgi-testclient",
        "transport_note": (
            "HTTP timings are Starlette TestClient against the real app on this host. "
            "A kernel TCP bind was not used because this environment forbids loopback sockets."
        ),
    }
    started = time.perf_counter()
    health = client.get("/v1/health")
    out["health_ms"] = _ms(started)
    out["health_status"] = health.json().get("status")
    started = time.perf_counter()
    caps = client.get("/v1/capabilities")
    out["capabilities_ms"] = _ms(started)
    out["capabilities_status"] = caps.status_code
    started = time.perf_counter()
    ui = client.get("/")
    out["ui_first_byte_ms"] = _ms(started)
    out["ui_status"] = ui.status_code
    files = {"images": ("ref.png", _png(), "image/png")}
    started = time.perf_counter()
    created = client.post(
        "/v1/searches",
        files=files,
        data={"text": "Dior Homme General Army Trainer 07", "tags": "dior"},
    )
    out["search_create_ms"] = _ms(started)
    out["search_create_status"] = created.status_code
    search_id = created.json().get("search_id")
    out["search_id"] = search_id
    first_progress_ms: float | None = None
    first_candidate_ms: float | None = None
    first_result_ms: float | None = None
    campaign_wall_ms: float | None = None
    poll_started = time.perf_counter()
    deadline = time.time() + 45.0
    while time.time() < deadline:
        body = client.get(f"/v1/searches/{search_id}").json()
        elapsed = _ms(poll_started)
        progress = body.get("progress") or {}
        if first_progress_ms is None and (progress.get("stage") or body.get("state") != "CREATED"):
            first_progress_ms = elapsed
        results = client.get(f"/v1/searches/{search_id}/results").json()
        public_rows = list(results.get("real") or []) + list(results.get("possibly_real") or [])
        if first_result_ms is None and public_rows:
            first_result_ms = elapsed
        if first_candidate_ms is None:
            counts = body.get("counts") or {}
            coverage = body.get("coverage") or {}
            counted = any(int(counts.get(key) or 0) for key in ("real", "possibly_real", "hidden"))
            normalized = int(coverage.get("candidates_normalized") or 0) > 0
            if counted or normalized:
                first_candidate_ms = elapsed
        if body.get("terminal_status"):
            campaign_wall_ms = elapsed
            break
        time.sleep(0.02)
    out["first_progress_event_ms"] = first_progress_ms
    out["first_candidate_ms"] = first_candidate_ms
    out["first_routed_result_ms"] = first_result_ms
    out["campaign_wall_ms"] = campaign_wall_ms
    return out


def _session(data_root: Path) -> tuple[Database, CampaignController]:
    settings = Settings.from_env(data_root=data_root)
    settings.ensure_data_root()
    db = Database(settings.db_path)
    migrate(db, settings.migrations_dir)
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    return db, CampaignController(db, store, settings)


def _cost_summary(controller: CampaignController, search_id: str) -> dict[str, Any]:
    receipts = [
        row
        for row in controller.repos.list_receipts(search_id)
        if row.get("receipt_type") == "CostReceipt"
    ]
    fetches = len(controller.repos.list_fetch_attempts(search_id))
    cache_hits = sum(int(row.get("cache_hits") or 0) for row in receipts)
    usage = controller.usage(search_id).snapshot()
    return {
        "fetches": fetches,
        "cache_hits": cache_hits,
        "receipts": [
            {
                "phase": (row.get("payload") or {}).get("phase"),
                "cache_hits": row.get("cache_hits"),
                "fetches": (row.get("payload") or {}).get("fetches"),
            }
            for row in receipts
        ],
        "budget": usage.get("committed"),
        "candidates": len(controller.repos.list_candidates(search_id)),
        "results": len(controller.repos.list_results(search_id)),
    }


def _measure_fixture(data_root: Path) -> dict[str, Any]:
    db, controller = _session(data_root)
    try:
        runner = FixtureRunner(controller)
        cold_started = time.perf_counter()
        first = runner.create("dior_minimal")
        first_candidate = None
        first_result = None
        create_ms = _ms(cold_started)
        run_started = time.perf_counter()
        runner.run(first.search_id)
        wall = _ms(run_started)
        events = controller.repos.list_events(first.search_id)
        origin = parse_utc_or_now(controller, first.search_id)
        for event in events:
            name = str(event.get("event_name") or "")
            ts = event.get("timestamp")
            elapsed = None
            if ts:
                from searcher.core.time import parse_utc

                try:
                    elapsed = (parse_utc(str(ts)) - origin).total_seconds() * 1000.0
                except Exception:
                    elapsed = None
            if name == "candidate.discovered" and first_candidate is None:
                first_candidate = elapsed
            if str(name).startswith("result.") and first_result is None:
                first_result = elapsed
        cold = {
            "search_create_ms": create_ms,
            "campaign_wall_ms": wall,
            "first_candidate_ms": None if first_candidate is None else round(first_candidate, 3),
            "first_routed_result_ms": None if first_result is None else round(first_result, 3),
            **_cost_summary(controller, first.search_id),
        }
        warm_started = time.perf_counter()
        second = runner.create("dior_minimal")
        runner.run(second.search_id)
        warm_wall = _ms(warm_started)
        runtime = controller.repos.get_runtime(second.search_id)
        warm_events = controller.repos.list_events(second.search_id)
        warm_first_candidate = None
        warm_first_result = None
        warm_origin = parse_utc_or_now(controller, second.search_id)
        for event in warm_events:
            name = str(event.get("event_name") or "")
            ts = event.get("timestamp")
            elapsed = None
            if ts:
                from searcher.core.time import parse_utc

                try:
                    elapsed = (parse_utc(str(ts)) - warm_origin).total_seconds() * 1000.0
                except Exception:
                    elapsed = None
            if name == "candidate.discovered" and warm_first_candidate is None:
                warm_first_candidate = elapsed
            if str(name).startswith("result.") and warm_first_result is None:
                warm_first_result = elapsed
        warm = {
            "campaign_wall_ms": warm_wall,
            "first_candidate_ms": None
            if warm_first_candidate is None
            else round(warm_first_candidate, 3),
            "first_routed_result_ms": None
            if warm_first_result is None
            else round(warm_first_result, 3),
            "index_hits": runtime.get("index_hits"),
            "index_skip_source_work": runtime.get("index_skip_source_work"),
            **_cost_summary(controller, second.search_id),
        }
        avoidance = 0.0
        if cold["fetches"]:
            avoidance = 1.0 - (warm["fetches"] / max(1, cold["fetches"]))
        return {
            "cold": cold,
            "warm": warm,
            "duplicate_work_avoided": round(avoidance, 4),
            "cache_hit_rate_warm": (
                round(warm["cache_hits"] / max(1, warm["cache_hits"] + warm["fetches"]), 4)
            ),
        }
    finally:
        db.close()


def parse_utc_or_now(controller: CampaignController, search_id: str) -> Any:
    from searcher.core.time import parse_utc, utc_now

    campaign = controller.repos.get_campaign(search_id)
    if campaign is None:
        return utc_now()
    # created_at is not on SearchCampaign; use first event.
    events = controller.repos.list_events(search_id)
    if events:
        return parse_utc(str(events[0]["timestamp"]))
    return utc_now()


def _profile_get_campaign(data_root: Path) -> dict[str, Any]:
    db, controller = _session(data_root)
    try:
        runner = FixtureRunner(controller)
        intent = runner.create("dior_minimal")
        runner.run(intent.search_id)
        search_id = intent.search_id
        repos = controller.repos
        started = time.perf_counter()
        for _ in range(200):
            repos.get_campaign(search_id)
        get_campaign_ms = _ms(started)
        started = time.perf_counter()
        for _ in range(200):
            repos.get_state_version(search_id)
        state_version_ms = _ms(started)
        return {
            "get_campaign_200x_ms": get_campaign_ms,
            "get_state_version_200x_ms": state_version_ms,
            "justification": (
                "emit() used to call get_campaign, which loads the intent and six "
                "child-id lists, on every public event. A json_group_array rewrite "
                "of those lists was slower on this host (tiny rows, six correlated "
                "subqueries). emit() now reads only state_version."
            ),
        }
    finally:
        db.close()


def _profile_decode() -> dict[str, Any]:
    png = _png()
    started = time.perf_counter()
    for index in range(24):
        open_rgb(_png((index, 40, 60)))
    unique_ms = _ms(started)
    started = time.perf_counter()
    for _ in range(24):
        open_rgb(png)
    repeat_ms = _ms(started)
    return {
        "open_rgb_24x_unique_ms": unique_ms,
        "open_rgb_24x_same_ms": repeat_ms,
        "justification": (
            "matching and cheap signals re-open the same listing PNG. "
            "An LRU keyed by content digest avoids that decode on the repeat path."
        ),
    }


def run(output: Path) -> dict[str, Any]:
    import socket as _socket

    host = _socket.gethostname()
    http_root = Path(tempfile.mkdtemp(prefix="searcher-bench-http-"))
    fixture_root = Path(tempfile.mkdtemp(prefix="searcher-bench-fx-"))
    with _client(http_root) as client:
        http_cold = _measure_http(client)
    # Populate the same data root so a second HTTP search can hit the index.
    _measure_fixture(http_root)
    with _client(http_root) as client:
        http_warm = _measure_http(client)
    http_metrics = {"cold": http_cold, "warm": http_warm}
    fixture_metrics = _measure_fixture(fixture_root)
    profile = {
        "get_campaign": _profile_get_campaign(fixture_root),
        "image_decode": _profile_decode(),
    }
    payload = {
        "host": host,
        "http": http_metrics,
        "fixture": fixture_metrics,
        "profile": profile,
    }
    write_receipt(output, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure Searcher latency on this host")
    parser.add_argument(
        "--output",
        default="artifacts/searcher-performance.receipt.json",
        help="path for the performance receipt",
    )
    args = parser.parse_args(argv)
    payload = run(Path(args.output))
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
