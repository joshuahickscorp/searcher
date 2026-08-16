"""A stalling source is abandoned with a recorded reason; the campaign ends."""

from __future__ import annotations

import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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

STALL_SECONDS = 60.0
SOURCE_DEADLINE = 1.2
REQUEST_TIMEOUT = 0.35
STALL_BASE = "http://127.0.0.1:0"
_STALL_STOP = threading.Event()


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
    run_text = " ".join(str(row) for row in runs)
    blob = f"{abandoned} {warning_text} {run_text}"
    assert DEADLINE_REASON in blob or "deadline" in blob.lower()
    assert "stall" in blob

    # The stalling URL must not have been treated as a successful empty search.
    assert abandoned or DEADLINE_REASON in blob
