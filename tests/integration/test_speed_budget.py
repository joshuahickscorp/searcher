"""Speed-lane budget: stall abandon, host-capped overlap, batch embed, warm path."""

from __future__ import annotations

import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import pytest
from tests.support.offline_shop import tiny_png

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.events import list_events
from searcher.campaigns.orchestrator import CampaignOrchestrator
from searcher.campaigns.states import is_terminal
from searcher.contracts.enums import Availability, FetchMode, SourceAdmission, SourceOutcome
from searcher.contracts.models import (
    ListingCandidate,
    LiveStatus,
    QueryVariant,
    RatePolicy,
    RawListing,
    SourceHealth,
    SourceManifest,
)
from searcher.core.time import utc_now
from searcher.normalization.listing import normalize_raw
from searcher.sources.adapters.protocol import DiscoveryPageResult
from searcher.sources.fetch_modes import FetchedDocument
from searcher.sources.manifest import build_manifest
from searcher.workers.api_campaign import create_api_campaign
from searcher.workers.bounded_discovery import DEADLINE_REASON, install_bounded_discovery
from searcher.workers.host_io import map_by_host
from searcher.workers.vision.worker import _embed_batch, run_vision_worker

SOURCE_DEADLINE = 1.2
REQUEST_TIMEOUT = 0.35
STALL_SECONDS = 60.0
_STALL_STOP = threading.Event()
STALL_BASE = "http://127.0.0.1:0"


class _StallHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/robots.txt":
            body = b"User-agent: *\nAllow: /\nCrawl-delay: 0\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        _STALL_STOP.wait(timeout=STALL_SECONDS)
        body = b"never"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class StallAdapter:
    def __init__(self) -> None:
        host = urlparse(STALL_BASE).netloc or "127.0.0.1"
        self._manifest = build_manifest(
            source_id="stall",
            adapter="stall",
            domain=host,
            access_method="http_get",
            admission_status=SourceAdmission.ADMITTED,
            allowed_use="deadline test",
            source_class="consignment",
            languages=["en"],
            listing_path_prefixes=["/stall"],
            fetch_modes=[FetchMode.CACHE, FetchMode.HTTP],
            rate_policy=RatePolicy(requests_per_minute=120, burst=8, concurrent=1),
        )
        self.escalator = None

    def manifest(self) -> SourceManifest:
        return self._manifest

    def health_check(self) -> SourceHealth:
        return SourceHealth(
            source_id="stall",
            last_outcome=SourceOutcome.NOT_ATTEMPTED,
            last_checked_at=utc_now(),
        )

    def discover(self, query: QueryVariant, cursor: str | None) -> DiscoveryPageResult:
        del query, cursor
        return DiscoveryPageResult(
            [f"{STALL_BASE}/stall"],
            [],
            None,
            SourceOutcome.NOT_ATTEMPTED.value,
            "stall seed",
        )

    def parse(self, fetch: FetchedDocument) -> list[RawListing]:
        del fetch
        return []

    def normalize(self, raw: RawListing) -> ListingCandidate:
        return normalize_raw(raw)

    def live_check(self, candidate: ListingCandidate) -> LiveStatus:
        del candidate
        return LiveStatus(availability=Availability.UNKNOWN, checked_at=utc_now())


@pytest.fixture
def stall_server() -> Any:
    previous = os.environ.get("SEARCHER_ALLOW_LOOPBACK")
    os.environ["SEARCHER_ALLOW_LOOPBACK"] = "1"
    _STALL_STOP.clear()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _StallHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    global STALL_BASE
    STALL_BASE = f"http://{host}:{port}"
    from searcher.sources.adapters import ADAPTER_REGISTRY

    ADAPTER_REGISTRY["stall"] = StallAdapter
    import searcher.sources.engine as engine_mod

    previous_engine = engine_mod.DiscoveryEngine
    try:
        yield STALL_BASE
    finally:
        ADAPTER_REGISTRY.pop("stall", None)
        engine_mod.DiscoveryEngine = previous_engine
        from searcher.workers.bounded_discovery import BoundedDiscoveryEngine

        BoundedDiscoveryEngine._default_source_deadline = None
        BoundedDiscoveryEngine._default_request_timeout = None
        _STALL_STOP.set()
        httpd.shutdown()
        thread.join(timeout=2)
        if previous is None:
            os.environ.pop("SEARCHER_ALLOW_LOOPBACK", None)
        else:
            os.environ["SEARCHER_ALLOW_LOOPBACK"] = previous


@pytest.mark.timeout(20)
def test_stalling_source_is_abandoned_and_campaign_terminates(
    controller: CampaignController, stall_server: str
) -> None:
    del stall_server
    install_bounded_discovery(
        source_deadline_seconds=SOURCE_DEADLINE,
        request_timeout_seconds=REQUEST_TIMEOUT,
    )
    search_id = create_api_campaign(
        controller,
        uploads=[(tiny_png(), "ref.png")],
        text="Archive Alpha Trainer 2007",
        tags=["archive"],
        client_search_id=None,
        settings=controller.settings,
    )
    started = time.monotonic()
    CampaignOrchestrator(
        controller, source_names=["stall"], max_rounds=1, max_work=2, batch_size=1
    ).run(search_id)
    elapsed = time.monotonic() - started
    campaign = controller.get(search_id)
    assert elapsed < 8.0
    assert is_terminal(campaign.state)
    assert campaign.terminal_status is not None
    assert campaign.terminal_status.value != "FAILED"

    runtime = controller.repos.get_runtime(search_id)
    abandoned = runtime.get("abandoned_sources") or []
    events = list_events(controller.repos, search_id)
    warning_text = " ".join(
        str(event.payload)
        for event in events
        if "warning" in event.event_name or "progress" in event.event_name
    )
    runs = controller.repos.list_source_runs(search_id)
    blob = f"{abandoned} {warning_text} {runs}"
    assert DEADLINE_REASON in blob or "deadline" in blob.lower()
    assert "stall" in blob
    assert abandoned or DEADLINE_REASON in blob
    assert any(
        isinstance(row, dict) and "deadline" in str(row.get("reason", "")).lower()
        for row in abandoned
    ) or DEADLINE_REASON in blob


def test_map_by_host_overlaps_hosts_and_serializes_one_host() -> None:
    lock = threading.Lock()
    inflight = {"a": 0, "b": 0}
    peak = {"a": 0, "b": 0}

    def work(item: tuple[str, int]) -> int:
        host, value = item
        with lock:
            inflight[host] += 1
            peak[host] = max(peak[host], inflight[host])
        time.sleep(0.08)
        with lock:
            inflight[host] -= 1
        return value

    items = [("a", 1), ("a", 2), ("b", 3), ("b", 4)]
    started = time.monotonic()
    out = map_by_host(items, work, host_of_item=lambda item: item[0], default_cap=1)
    elapsed = time.monotonic() - started
    assert out == [1, 2, 3, 4]
    assert peak["a"] == 1
    assert peak["b"] == 1
    # Four serial 80ms sleeps would be ~320ms. Two hosts at cap 1 overlap.
    assert elapsed < 0.28


def test_map_by_host_respects_per_item_cap() -> None:
    lock = threading.Lock()
    peak = {"h": 0}
    inflight = {"h": 0}

    def work(item: tuple[str, int]) -> int:
        host, value = item
        with lock:
            inflight[host] += 1
            peak[host] = max(peak[host], inflight[host])
        time.sleep(0.05)
        with lock:
            inflight[host] -= 1
        return value

    items = [("h", 1), ("h", 2), ("h", 3)]
    out = map_by_host(
        items, work, host_of_item=lambda item: item[0], cap_of=lambda _item: 2, default_cap=1
    )
    assert out == [1, 2, 3]
    assert peak["h"] == 2
    assert peak["h"] <= 2


def test_vision_worker_embeds_images_in_one_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.helpers_matching import make_candidate, make_hypothesis

    calls: list[int] = []

    def fake_resolve() -> object:
        return SimpleNamespace(identity="stub", weights_path="/tmp/none")

    def fake_embed_pngs(pngs: list[bytes], resolved: object | None = None) -> list[None]:
        del resolved
        calls.append(len(pngs))
        return [None] * len(pngs)

    monkeypatch.setattr("searcher.retrieval.embeddings.resolve_backend", fake_resolve)
    monkeypatch.setattr("searcher.retrieval.embeddings.embed_pngs", fake_embed_pngs)
    monkeypatch.setattr(
        "searcher.workers.vision.worker.judge_candidates",
        lambda **_kwargs: SimpleNamespace(decisions=[]),
    )

    hyp = make_hypothesis(category="garment")
    true_c, _ = make_candidate(candidate_id="true", title="WILLY CHAVARRIA long sleeve")
    ref = {"r": tiny_png((10, 20, 30))}
    cands = {"true": {"a": tiny_png((11, 21, 31)), "b": tiny_png((12, 22, 32))}}
    _embed_batch(ref, cands)
    assert calls == [3]
    run_vision_worker(
        search_id="s",
        hypothesis=hyp,
        candidates=[true_c],
        reference_pngs=ref,
        candidate_pngs=cands,
    )
    assert calls[-1] == 3
    assert max(calls) >= 3


def test_warm_repeat_uses_index_and_stays_fast(controller: CampaignController) -> None:
    from pathlib import Path

    from searcher.campaigns.runner import FixtureRunner

    if not (Path.cwd() / "fixtures" / "dior_minimal").is_dir():
        pytest.skip("dior_minimal fixture is not on disk")
    runner = FixtureRunner(controller)
    first = runner.create("dior_minimal")
    runner.run(first.search_id)
    started = time.perf_counter()
    second = runner.create("dior_minimal")
    runner.run(second.search_id)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    fetches_2 = len(controller.repos.list_fetch_attempts(second.search_id))
    runtime = controller.repos.get_runtime(second.search_id)
    assert fetches_2 == 0
    assert runtime.get("index_skip_source_work") is True
    assert int(runtime.get("index_hits") or 0) >= 1
    # Warm repeat target is 1000ms; this host's index path is tens of ms.
    assert elapsed_ms < 1000.0


def test_merge_runtime_does_not_drop_concurrent_keys(controller: CampaignController) -> None:
    search_id = create_api_campaign(
        controller,
        uploads=[(tiny_png(), "ref.png")],
        text="merge",
        tags=["t"],
        client_search_id=None,
        settings=controller.settings,
    )
    errors: list[str] = []

    def writer(key: str, value: int) -> None:
        try:
            controller.repos.merge_runtime(search_id, {key: value})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [
        threading.Thread(target=writer, args=("alpha", 1)),
        threading.Thread(target=writer, args=("beta", 2)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    runtime = controller.repos.get_runtime(search_id)
    assert runtime.get("alpha") == 1
    assert runtime.get("beta") == 2
    controller.repos.append_runtime_list(search_id, "abandoned_sources", {"source": "x"})
    controller.repos.append_runtime_list(search_id, "abandoned_sources", {"source": "y"})
    abandoned = controller.repos.get_runtime(search_id).get("abandoned_sources")
    assert isinstance(abandoned, list)
    assert len(abandoned) == 2
