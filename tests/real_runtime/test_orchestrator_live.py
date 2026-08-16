"""Live campaign against admitted public sources. Honest outcome is the result.

Runs in its own pytest invocation. On macOS this test leaves the interpreter unable
to spawn a child process: a subsequent `subprocess.run` returns -11 (SIGSEGV) even
though only MainThread is alive, which is the fork-after-framework-initialisation
crash. It breaks any later test that shells out (`test_serve_shared`,
`test_probe_and_import`). The underlying cause is not yet identified — see G039 —
so the interaction is quarantined rather than papered over with
OBJC_DISABLE_INITIALIZE_FORK_SAFETY.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.support.offline_shop import tiny_png

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.events import list_events
from searcher.campaigns.orchestrator import CampaignOrchestrator
from searcher.receipts.types import typed_from_payload
from searcher.workers.api_campaign import create_api_campaign

pytestmark = pytest.mark.live_campaign


@pytest.mark.timeout(180)
def test_live_orchestrator_campaign(controller: CampaignController) -> None:
    images = []
    fixtures = Path("fixtures/images")
    if fixtures.is_dir():
        for path in sorted(fixtures.glob("*.png"))[:3]:
            images.append((path.read_bytes(), path.name))
    if not images:
        images = [(tiny_png(), "ref.png")]
    search_id = create_api_campaign(
        controller,
        uploads=images,
        text="Dior Homme Army Trainer",
        tags=["dior", "footwear", "2007"],
        client_search_id=None,
        settings=controller.settings,
    )
    sources = ["wikimedia", "kind", "komehyo", "ebay"]
    CampaignOrchestrator(
        controller, source_names=sources, max_rounds=1, max_work=6, batch_size=2
    ).run(search_id)
    campaign = controller.get(search_id)
    queries = controller.repos.list_queries(search_id)
    by_lang: dict[str, list[str]] = {}
    for query in queries:
        by_lang.setdefault(query.language, []).append(query.query_text)
    runs = controller.repos.list_source_runs(search_id)
    candidates = controller.repos.list_candidates(search_id)
    decisions = controller.repos.list_decisions(search_id)
    results = controller.repos.list_results(search_id)
    counts = {"real": 0, "possibly_real": 0, "hidden": 0}
    for row in results:
        bucket = str(row["public_bucket"])
        if bucket in counts:
            counts[bucket] += 1
    receipts = controller.repos.list_receipts(search_id)
    exhaustion_rows = [row for row in receipts if row["receipt_type"] == "SearchExhaustionReceipt"]
    print("LIVE_SEARCH_ID", search_id)
    print("LIVE_STATE", campaign.state.value)
    print("LIVE_TERMINAL", campaign.terminal_status.value if campaign.terminal_status else None)
    print("LIVE_REASON", campaign.terminal_reason)
    print("LIVE_QUERIES_BY_LANG", json.dumps(by_lang, ensure_ascii=False))
    print(
        "LIVE_SOURCE_RUNS",
        json.dumps(
            [{"source": row.get("source_id"), "outcome": row.get("last_outcome")} for row in runs],
            sort_keys=True,
        ),
    )
    print("LIVE_CANDIDATES", len(candidates))
    print("LIVE_DECISIONS", len(decisions))
    print("LIVE_COUNTS", json.dumps(counts))
    for candidate in candidates[:12]:
        print("LIVE_URL", candidate.canonical_url, candidate.availability.value)
    if exhaustion_rows:
        receipt = typed_from_payload(exhaustion_rows[0])
        print("LIVE_EXHAUSTION", receipt.model_dump(mode="json"))
    events = list_events(controller.repos, search_id)
    print("LIVE_EVENT_COUNT", len(events))
    for event in events:
        if event.event_name.startswith("search.") or event.event_name.startswith("result."):
            print("LIVE_EVENT", event.event_name, event.payload)
    assert campaign.terminal_status is not None
    assert campaign.terminal_status.value != "FAILED"
    assert queries
    assert "en" in by_lang
    assert campaign.search_exhaustion_receipt or campaign.state.value == "BLOCKED"
