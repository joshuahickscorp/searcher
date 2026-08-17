"""Per-stage and per-source timing for a live campaign on this host.

Does not change campaign behaviour. Writes artifacts/searcher-latency.receipt.json
when invoked as a phase of scripts/bench_stage_latency.sh.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import socket
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.events import list_events
from searcher.campaigns.orchestrator import STAGE_LANGUAGE, CampaignOrchestrator
from searcher.core.config import Settings
from searcher.core.time import format_utc, utc_now
from searcher.evidence.content_store import ContentStore
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate
from searcher.workers.api_campaign import create_api_campaign

DEFAULT_TEXT = "Dior Homme General Army Trainer 07"
DEFAULT_TAGS = ["footwear"]
API_SOURCES = [
    "wikimedia",
    "kind",
    "komehyo",
    "the_realreal",
    "byronesque",
    "heroine",
    "ebay",
]
PROBE_URLS = {
    "wikimedia": "https://en.wikipedia.org/robots.txt",
    "kind": "https://shop.kind.co.jp/robots.txt",
    "komehyo": "https://komehyo.jp/robots.txt",
    "the_realreal": "https://www.therealreal.com/robots.txt",
    "byronesque": "https://byronesque.com/robots.txt",
    "heroine": "https://shopheroine.com/robots.txt",
}


def _png(color: tuple[int, int, int] = (20, 40, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(buf, format="PNG")
    return buf.getvalue()


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)


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


def _reference_bytes() -> bytes:
    fixtures = Path("fixtures/images")
    if fixtures.is_dir():
        for path in sorted(fixtures.glob("*.png")):
            return path.read_bytes()
    return _png()


def probe_hosts(*, timeout: float = 8.0) -> dict[str, Any]:
    """One GET per admitted host. Records connect/read vs hang."""
    import httpx

    out: dict[str, Any] = {}
    for name, url in PROBE_URLS.items():
        started = time.perf_counter()
        try:
            response = httpx.get(
                url,
                timeout=httpx.Timeout(timeout, connect=min(5.0, timeout)),
                follow_redirects=True,
                headers={"User-Agent": "Searcher-latency-probe/0.1"},
            )
            body = response.text
            crawl = None
            for line in body.splitlines():
                if line.lower().startswith("crawl-delay"):
                    crawl = line.split(":", 1)[-1].strip()
                    break
            out[name] = {
                "url": url,
                "status": response.status_code,
                "elapsed_ms": _ms(started),
                "bytes": len(response.content),
                "crawl_delay": crawl,
            }
        except Exception as exc:
            out[name] = {
                "url": url,
                "status": None,
                "elapsed_ms": _ms(started),
                "error": f"{type(exc).__name__}: {exc}",
            }
    return out


def _stage_breakdown(controller: CampaignController, search_id: str) -> list[dict[str, Any]]:
    events = list_events(controller.repos, search_id)
    if not events:
        return []
    origin = events[0].timestamp
    rows: list[dict[str, Any]] = []
    last_stage: str | None = None
    last_at = origin
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        stage = None
        if event.event_name.endswith("search.progress") or event.event_name == "search.progress":
            stage = str(payload.get("stage") or payload.get("phase") or "")
        if event.event_name == "search.state":
            state = str(payload.get("state") or "")
            stage = STAGE_LANGUAGE.get(state, state)
        if not stage:
            continue
        if last_stage is not None and stage != last_stage:
            elapsed = (event.timestamp - last_at).total_seconds() * 1000.0
            rows.append(
                {
                    "stage": last_stage,
                    "elapsed_ms": round(elapsed, 3),
                }
            )
            last_at = event.timestamp
        if last_stage != stage:
            last_stage = stage
            last_at = event.timestamp
    if last_stage is not None and events:
        elapsed = (events[-1].timestamp - last_at).total_seconds() * 1000.0
        rows.append({"stage": last_stage, "elapsed_ms": round(elapsed, 3)})
    return rows


def _source_breakdown(controller: CampaignController, search_id: str) -> list[dict[str, Any]]:
    events = list_events(controller.repos, search_id)
    starts: dict[str, Any] = {}
    out: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        phase = str(payload.get("phase") or "")
        source = str(payload.get("source") or "")
        if not source:
            continue
        row = out.setdefault(
            source,
            {
                "source": source,
                "started_ms": None,
                "elapsed_ms": None,
                "outcome": None,
                "pages": 0,
                "fetches": 0,
            },
        )
        if phase == "source_start":
            starts[source] = event.timestamp
            if events:
                row["started_ms"] = round(
                    (event.timestamp - events[0].timestamp).total_seconds() * 1000.0, 3
                )
        elif phase == "source_complete":
            row["outcome"] = payload.get("outcome")
            if source in starts:
                row["elapsed_ms"] = round(
                    (event.timestamp - starts[source]).total_seconds() * 1000.0, 3
                )
        elif phase == "page_fetched":
            row["pages"] = int(row["pages"]) + 1
        elif event.event_name == "search.warning" and payload.get("basis"):
            row["reason"] = payload.get("basis")
            row["outcome"] = row.get("outcome") or payload.get("outcome")
    attempts = controller.repos.list_fetch_attempts(search_id)
    by_source: dict[str, list[float]] = {}
    for attempt in attempts:
        sid = attempt.source_id
        elapsed = (attempt.ended_at - attempt.started_at).total_seconds() * 1000.0
        by_source.setdefault(sid, []).append(elapsed)
        if sid in out:
            out[sid]["fetches"] = int(out[sid]["fetches"]) + 1
        else:
            out[sid] = {
                "source": sid,
                "started_ms": None,
                "elapsed_ms": None,
                "outcome": attempt.status.value,
                "pages": 0,
                "fetches": 1,
            }
    for sid, times in by_source.items():
        out[sid]["fetch_elapsed_ms"] = [round(t, 3) for t in times]
        out[sid]["fetch_wall_sum_ms"] = round(sum(times), 3)
        out[sid]["fetch_max_ms"] = round(max(times), 3)
    runs = controller.repos.list_source_runs(search_id)
    for run in runs:
        sid = str(run.get("source_id") or "")
        if not sid:
            continue
        row = out.setdefault(
            sid,
            {
                "source": sid,
                "started_ms": None,
                "elapsed_ms": None,
                "outcome": run.get("last_outcome"),
                "pages": 0,
                "fetches": 0,
            },
        )
        if not row.get("outcome"):
            row["outcome"] = run.get("last_outcome")
        payload = run.get("payload") or run.get("payload_json") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        if isinstance(payload, dict) and payload.get("pages") is not None:
            row["pages"] = payload.get("pages")
    return [out[key] for key in sorted(out)]


def _fetch_serial_stats(controller: CampaignController, search_id: str) -> dict[str, Any]:
    attempts = controller.repos.list_fetch_attempts(search_id)
    if not attempts:
        return {
            "fetches": 0,
            "network_wait_ms": 0.0,
            "serial_fetches": 0,
            "hosts": 0,
            "could_have_been_concurrent": 0,
        }
    by_host: dict[str, int] = {}
    wait = 0.0
    for attempt in attempts:
        host = urlparse(attempt.url).netloc
        by_host[host] = by_host.get(host, 0) + 1
        wait += (attempt.ended_at - attempt.started_at).total_seconds() * 1000.0
    return {
        "fetches": len(attempts),
        "network_wait_ms": round(wait, 3),
        "serial_fetches": len(attempts),
        "hosts": len(by_host),
        "could_have_been_concurrent": max(0, len(by_host) - 1),
        "per_host": by_host,
        "note": (
            "DiscoveryEngine._run_plan fetches one URL at a time, and engine.run "
            "walks sources one at a time. Hosts are independent; same-host fetches "
            "must stay serial under the source rate policy."
        ),
    }


def _dummy_embedding_weights(path: Path) -> bool:
    """Trace a tiny stand-in so batch vs serial can be timed without DINOv2."""
    try:
        import torch
    except ImportError:
        return False

    # Built with type() rather than a class statement: subclassing torch.nn.Module
    # directly makes `uv run mypy src` fail on a machine without torch installed,
    # where the base resolves to Any. That is every fresh clone, and mypy is a
    # documented gate command.
    def _forward(_self: Any, tensor: Any) -> Any:
        flat = tensor.reshape(tensor.shape[0], -1)
        width = int(flat.shape[1])
        reps = (384 + width - 1) // width
        return flat.repeat(1, reps)[:, :384]

    stub_cls: Any = type("_Stub", (torch.nn.Module,), {"forward": _forward})
    model = stub_cls()
    model.eval()
    with torch.inference_mode():
        jit_trace: Any = torch.jit.trace  # torch.jit is untyped for mypy
    traced = jit_trace(model, torch.zeros(1, 3, 224, 224))
    path.parent.mkdir(parents=True, exist_ok=True)
    traced.save(str(path))
    return True


def measure_embedding_throughput(*, batch: bool, n_images: int = 16) -> dict[str, Any]:
    """Images/sec for the retrieval embedding path on this host."""
    from searcher.retrieval import embeddings as emb

    pngs = [_png((i * 7 % 200, 40, 80)) for i in range(n_images)]
    backend = emb.resolve_backend()
    note = None
    dummy_dir: Path | None = None
    previous_weights = os.environ.get("SEARCHER_EMBEDDING_WEIGHTS")
    if backend is None:
        dummy_dir = Path(tempfile.mkdtemp(prefix="searcher-embed-dummy-"))
        dummy = dummy_dir / "embedding.pt"
        if _dummy_embedding_weights(dummy):
            os.environ["SEARCHER_EMBEDDING_WEIGHTS"] = str(dummy)
            emb._MODEL = None
            emb._VEC_CACHE.clear()
            backend = emb.resolve_backend()
            note = "synthetic stub weights; production has no local DINOv2 file"
        else:
            return {
                "available": False,
                "images": n_images,
                "images_per_second": 0.0,
                "elapsed_ms": 0.0,
                "batched": batch,
                "note": "no local embedding weights and torch is unavailable",
            }
    assert backend is not None
    # Warm the model once so load time is not in the rate.
    emb.embed_png(pngs[0], backend)
    emb._VEC_CACHE.clear()
    started = time.perf_counter()
    if batch and hasattr(emb, "embed_pngs"):
        emb.embed_pngs(pngs, backend)
    else:
        for png in pngs:
            emb.embed_png(png, backend)
    elapsed = time.perf_counter() - started
    ips = (n_images / elapsed) if elapsed > 0 else 0.0
    if previous_weights is None:
        os.environ.pop("SEARCHER_EMBEDDING_WEIGHTS", None)
    else:
        os.environ["SEARCHER_EMBEDDING_WEIGHTS"] = previous_weights
    if dummy_dir is not None:
        emb._MODEL = None
        emb._VEC_CACHE.clear()
    return {
        "available": True,
        "images": n_images,
        "images_per_second": round(ips, 3),
        "elapsed_ms": round(elapsed * 1000.0, 3),
        "batched": batch,
        "device": os.environ.get("SEARCHER_EMBEDDING_DEVICE") or "auto",
        "identity": backend.identity,
        "note": note,
    }


def measure_fixture_index(data_root: Path) -> dict[str, Any]:
    from searcher.bench.latency import _measure_fixture

    return _measure_fixture(data_root)


def run_live_campaign(
    *,
    use_worker_entry: bool,
    max_rounds: int = 2,
    max_work: int = 8,
    batch_size: int = 3,
) -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix="searcher-latency-live-"))
    db, controller = _session(root)
    try:
        search_id = create_api_campaign(
            controller,
            uploads=[(_reference_bytes(), "ref.png")],
            text=DEFAULT_TEXT,
            tags=list(DEFAULT_TAGS),
            client_search_id=None,
            settings=controller.settings,
        )
        started = time.perf_counter()
        if use_worker_entry:
            from searcher.workers.api_campaign import run_api_campaign

            run_api_campaign(controller, search_id)
        else:
            CampaignOrchestrator(
                controller,
                source_names=list(API_SOURCES),
                max_rounds=max_rounds,
                max_work=max_work,
                batch_size=batch_size,
            ).run(search_id)
        wall_ms = _ms(started)
        campaign = controller.get(search_id)
        stages = _stage_breakdown(controller, search_id)
        sources = _source_breakdown(controller, search_id)
        fetches = _fetch_serial_stats(controller, search_id)
        hang = None
        for stage in stages:
            discovering = stage["stage"] == "Searching international sources"
            if discovering and stage["elapsed_ms"] >= 90_000:
                hang = {
                    "stage": stage["stage"],
                    "elapsed_ms": stage["elapsed_ms"],
                    "sources": sources,
                }
                break
        if hang is None:
            # Still record the DISCOVERING language stage even if under 90s.
            for stage in stages:
                if stage["stage"] == "Searching international sources":
                    hang = {
                        "stage": stage["stage"],
                        "elapsed_ms": stage["elapsed_ms"],
                        "sources": sources,
                        "exceeded_90s": False,
                    }
        slowest = None
        if sources:
            slowest = max(sources, key=lambda row: float(row.get("elapsed_ms") or 0.0))
        runtime = controller.repos.get_runtime(search_id)
        return {
            "search_id": search_id,
            "wall_ms": wall_ms,
            "state": campaign.state.value,
            "terminal_status": (
                campaign.terminal_status.value if campaign.terminal_status else None
            ),
            "terminal_reason": campaign.terminal_reason,
            "stages": stages,
            "sources": sources,
            "fetches": fetches,
            "hang": hang,
            "slowest_source": slowest,
            "candidates": len(controller.repos.list_candidates(search_id)),
            "coverage": runtime.get("coverage"),
            "progress": runtime.get("progress"),
            "index_skip_source_work": runtime.get("index_skip_source_work"),
            "index_hits": runtime.get("index_hits"),
            "data_root": str(root),
        }
    finally:
        db.close()


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def run_phase(
    phase: str,
    *,
    runs: int,
    output: Path,
    use_worker_entry: bool,
) -> dict[str, Any]:
    existing: dict[str, Any] = {}
    if output.is_file():
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    probes = probe_hosts()
    live_runs: list[dict[str, Any]] = []
    for index in range(runs):
        print(f"{phase} live run {index + 1}/{runs}", flush=True)
        live_runs.append(run_live_campaign(use_worker_entry=use_worker_entry))
        print(
            json.dumps(
                {
                    "run": index + 1,
                    "wall_ms": live_runs[-1]["wall_ms"],
                    "terminal": live_runs[-1]["terminal_status"],
                    "slowest": live_runs[-1].get("slowest_source"),
                },
                default=str,
            ),
            flush=True,
        )
    walls = [float(item["wall_ms"]) for item in live_runs]
    fixture_root = Path(tempfile.mkdtemp(prefix="searcher-latency-fx-"))
    fixture = measure_fixture_index(fixture_root)
    embedding = measure_embedding_throughput(batch=(phase == "after"))
    embedding_serial = measure_embedding_throughput(batch=False)
    payload = {
        "runs": live_runs,
        "median_wall_ms": round(_median(walls), 3),
        "min_wall_ms": round(min(walls), 3) if walls else None,
        "max_wall_ms": round(max(walls), 3) if walls else None,
        "host_probes": probes,
        "fixture": fixture,
        "embedding": embedding,
        "embedding_serial": embedding_serial,
        "use_worker_entry": use_worker_entry,
        "runs_requested": runs,
    }
    body = {
        "host": socket.gethostname(),
        "measured_at": format_utc(utc_now()),
        **existing,
        phase: payload,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(body, indent=2, sort_keys=True, default=str) + "\n"
    output.write_text(rendered, encoding="utf-8")
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Per-stage live campaign timing")
    parser.add_argument("--phase", choices=("before", "after"), required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--output",
        default="artifacts/searcher-latency.receipt.json",
    )
    parser.add_argument(
        "--worker-entry",
        action="store_true",
        help="Run through run_api_campaign (after path, includes worker wrappers).",
    )
    args = parser.parse_args(argv)
    # Before: call CampaignOrchestrator the same way today's API worker does,
    # without installing wrappers. After: go through run_api_campaign.
    use_worker = bool(args.worker_entry) or args.phase == "after"
    run_phase(
        args.phase,
        runs=max(1, args.runs),
        output=Path(args.output),
        use_worker_entry=use_worker,
    )
    print(f"wrote {args.output} phase={args.phase}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
