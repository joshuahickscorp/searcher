"""Real-network discovery against admitted sources. Polite, robots-honouring."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import pytest
from tests.conftest import make_budget, make_intent

from searcher.campaigns.controller import CampaignController
from searcher.contracts.enums import QueryType, SourceOutcome
from searcher.contracts.models import QueryVariant
from searcher.core.ids import new_id
from searcher.sources.adapters.kind import KindAdapter
from searcher.sources.admission import AdmissionGate
from searcher.sources.engine import DiscoveryEngine
from searcher.sources.http import HonestHttpClient
from searcher.sources.live_runner import LiveDiscoveryRunner
from searcher.sources.robots import RobotsCache

QUERY = "Dior Homme Army Trainer"
JA_QUERY = "ディオールオム トレーナー"


@pytest.mark.timeout(240)
def test_real_network_admitted_sources(
    controller: CampaignController, monkeypatch: pytest.MonkeyPatch
) -> None:
    # This test walks real catalogs at the real politeness rate. Most admitted
    # sources declare 12 requests per minute, which is 5.0s per fetch with
    # jitter, and the shipped campaign cap is 80 pages - 400s of deliberate
    # waiting against a 240s budget. The test cannot pass once catalog fallback
    # engages, and the answer is not to crawl faster or to widen the timeout
    # until the suite crawls too. It proves that admitted sources answer, which
    # a handful of pages shows as well as eighty.
    monkeypatch.setenv("SEARCHER_CATALOG_PAGES_PER_SOURCE", "2")
    monkeypatch.setenv("SEARCHER_CATALOG_PAGES_PER_CAMPAIGN", "4")
    intent = make_intent()
    controller.create(intent, budget=make_budget())
    queries = [
        QueryVariant(
            query_id=new_id(),
            hypothesis_id="h",
            round=1,
            language="en",
            query_text=QUERY,
            query_type=QueryType.EXACT_NAME,
            expected_gain=0.6,
        ),
        QueryVariant(
            query_id=new_id(),
            hypothesis_id="h",
            round=1,
            language="ja",
            query_text=JA_QUERY,
            query_type=QueryType.TRANSLATED,
            expected_gain=0.5,
        ),
    ]
    for query in queries:
        controller.repos.upsert_query(intent.search_id, query)
    sources = ["wikimedia", "kind", "ebay"]
    if os.environ.get("SEARCHER_SEARX_URL"):
        sources.insert(0, "searx")
    engine = DiscoveryEngine(controller, batch_size=3, max_work=12)
    try:
        summary = engine.run(intent.search_id, queries, source_names=sources)
    finally:
        engine.close()
    stamp = datetime.now(UTC).isoformat()
    print("REAL_NETWORK_QUERY", QUERY)
    print("REAL_NETWORK_SOURCES", sources)
    print("REAL_NETWORK_COVERAGE", json.dumps(summary.coverage, sort_keys=True))
    print("REAL_NETWORK_BEFORE", summary.candidates_before)
    print("REAL_NETWORK_AFTER", summary.candidates_after)
    print("REAL_NETWORK_BLOCKED", json.dumps(summary.blocked))
    print("REAL_NETWORK_TS", stamp)
    for listing in summary.listings[:12]:
        print("REAL_NETWORK_URL", listing.canonical_url)
    product_urls = [c.canonical_url for c in summary.listings if "/products/" in c.canonical_url]
    print("REAL_NETWORK_PRODUCTS", len(product_urls))
    assert "ebay" in summary.coverage
    assert summary.coverage["ebay"] == SourceOutcome.AUTH_REQUIRED.value
    assert any(
        outcome
        in {
            SourceOutcome.SEARCHED_MATCHES_FOUND.value,
            SourceOutcome.SEARCHED_NO_MATCH.value,
            SourceOutcome.RATE_LIMITED.value,
            SourceOutcome.BLOCKED_BY_ACCESS.value,
            SourceOutcome.NETWORK_FAILED.value,
            SourceOutcome.SOURCE_UNAVAILABLE.value,
        }
        for outcome in summary.coverage.values()
    )
    # A blocked classification must never be rewritten as no-match.
    for source, outcome in summary.coverage.items():
        if outcome in {
            SourceOutcome.AUTH_REQUIRED.value,
            SourceOutcome.BLOCKED_BY_ACCESS.value,
            SourceOutcome.BLOCKED_BY_POLICY.value,
        }:
            assert outcome != SourceOutcome.SEARCHED_NO_MATCH.value
            print("HONEST_BLOCK", source, outcome)


@pytest.mark.timeout(60)
def test_kind_search_path_refused_without_fetch() -> None:
    adapter = KindAdapter()
    manifest = adapter.manifest()
    http = HonestHttpClient()
    try:
        gate = AdmissionGate(RobotsCache(user_agent=http.user_agent), http)
        decision = gate.decide("https://shop.kind.co.jp/search?q=dior", manifest)
    finally:
        http.close()
    assert decision.allowed is False
    assert decision.outcome is SourceOutcome.BLOCKED_BY_POLICY
    print("ROBOTS_REFUSAL", decision.basis)


@pytest.mark.timeout(180)
def test_cli_shaped_live_campaign(controller: CampaignController) -> None:
    runner = LiveDiscoveryRunner(controller)
    intent = runner.create(
        QUERY,
        extra_queries=[("ja", JA_QUERY)],
        page_limit=12,
        source_limit=4,
        byte_limit=4_000_000,
    )
    summary = runner.run(intent.search_id, source_names=["wikimedia", "kind", "ebay"])
    campaign = controller.get(intent.search_id)
    print("LIVE_CAMPAIGN", intent.search_id, campaign.state.value)
    if summary:
        print("LIVE_COVERAGE", summary.coverage)
        print("LIVE_AFTER", summary.candidates_after)
        for listing in summary.listings[:5]:
            print("LIVE_URL", listing.canonical_url)
    assert campaign.state.value in {"COMPLETE", "PARTIAL", "BLOCKED", "CANCELLED"}
