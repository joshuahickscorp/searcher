"""Create-form scopes, results payload, and SSE carry the replica bucket."""

from __future__ import annotations

import io
from typing import Any

from PIL import Image
from tests.integration.test_api import parse_sse, wait_terminal

from searcher.contracts.enums import (
    Availability,
    BucketInternal,
    BucketPublic,
    FactClass,
    FactOrigin,
    PublicEventName,
)
from searcher.contracts.models import BucketDecision, BucketDecisionFields, ListingCandidate
from searcher.contracts.primitives import classified
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.ranking.vetoes import SELF_DECLARED_REPLICA

_TS = parse_utc("2007-06-15T12:00:00+00:00")


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), (12, 24, 36)).save(buf, format="PNG")
    return buf.getvalue()


def _create(client: Any, scopes: list[str] | None = None) -> Any:
    files: list[tuple[str, Any]] = [
        ("images", ("ref.png", _png(), "image/png")),
        ("text", (None, "Dior Homme General Army Trainer")),
        ("tags", (None, "dior")),
    ]
    if scopes is not None:
        for scope in scopes:
            files.append(("source_scopes", (None, scope)))
    return client.post("/v1/searches", files=files)


def _candidate(source_adapter: str, title: str) -> ListingCandidate:
    return ListingCandidate(
        candidate_id=new_id(),
        canonical_url=f"https://{source_adapter}.example/item/{new_id()[:8]}",
        source_adapter=source_adapter,
        title=classified(title, FactClass.REPORTED_BY_SELLER, FactOrigin.SELLER),
        availability=Availability.LIVE,
        first_seen_at=_TS,
        last_checked_at=_TS,
    )


def _decision(
    candidate_id: str,
    public: BucketPublic,
    internal: BucketInternal,
    *,
    reasons: list[str],
    vetoes: list[str] | None = None,
) -> BucketDecision:
    return BucketDecision(
        candidate_id=candidate_id,
        decision=BucketDecisionFields(internal=internal, public=public),
        policy_version="matching-1",
        item_match_lower_bound=0.94,
        authenticity_lower_bound=0.88,
        evidence_completeness=0.75,
        hard_vetoes=vetoes or [],
        reason_codes=reasons,
    )


def test_absent_source_scopes_stores_legitimate_default(api_app: tuple[Any, Any]) -> None:
    client, app = api_app
    created = _create(client)
    assert created.status_code == 201
    search_id = created.json()["search_id"]
    runtime = app.state.searcher.controller.repos.get_runtime(search_id)
    assert runtime.get("source_scopes", ["legitimate"]) == ["legitimate"]


def test_unknown_scopes_are_ignored_and_not_fatal(api_app: tuple[Any, Any]) -> None:
    client, app = api_app
    created = _create(client, scopes=["not-a-scope", "also-wrong"])
    assert created.status_code == 201
    search_id = created.json()["search_id"]
    runtime = app.state.searcher.controller.repos.get_runtime(search_id)
    assert runtime.get("source_scopes", ["legitimate"]) == ["legitimate"]


def test_both_scopes_are_stored(api_app: tuple[Any, Any]) -> None:
    client, app = api_app
    created = _create(client, scopes=["legitimate", "replica"])
    assert created.status_code == 201
    search_id = created.json()["search_id"]
    runtime = app.state.searcher.controller.repos.get_runtime(search_id)
    assert runtime["source_scopes"] == ["legitimate", "replica"]


def test_results_payload_and_sse_carry_three_lists(api_app: tuple[Any, Any]) -> None:
    client, app = api_app
    created = _create(client, scopes=["legitimate", "replica"])
    search_id = created.json()["search_id"]
    wait_terminal(client, search_id)
    controller = app.state.searcher.controller

    real = _candidate("ebay", "Dior Homme General Army Trainer")
    possible = _candidate("the_realreal", "Dior Homme trainer similar pair")
    replica = _candidate("yupoo", "Unauthorized replica 1:1 of the trainer")
    controller.repos.upsert_candidate(search_id, real)
    controller.repos.upsert_candidate(search_id, possible)
    controller.repos.upsert_candidate(search_id, replica)
    controller.repos.insert_decision(
        search_id,
        new_id(),
        _decision(
            real.candidate_id,
            BucketPublic.REAL,
            BucketInternal.REAL,
            reasons=["real-gate"],
        ),
    )
    controller.repos.insert_decision(
        search_id,
        new_id(),
        _decision(
            possible.candidate_id,
            BucketPublic.POSSIBLY_REAL,
            BucketInternal.POSSIBLY_REAL,
            reasons=["possibly-real-gate"],
        ),
    )
    controller.repos.insert_decision(
        search_id,
        new_id(),
        _decision(
            replica.candidate_id,
            BucketPublic.HIDDEN,
            BucketInternal.REJECTED,
            reasons=[SELF_DECLARED_REPLICA, "hidden"],
            vetoes=[SELF_DECLARED_REPLICA],
        ),
    )
    from searcher.campaigns.orchestrator import CampaignOrchestrator

    CampaignOrchestrator(controller)._publish(search_id)

    payload = client.get(f"/v1/searches/{search_id}/results").json()
    assert [row["bucket"] for row in payload["real"]] == ["real"]
    assert [row["bucket"] for row in payload["possibly_real"]] == ["possibly_real"]
    assert "replica" in payload
    assert [row["bucket"] for row in payload["replica"]] == ["replica"]
    assert payload["replica"][0]["candidate_id"] == replica.candidate_id
    assert payload["replica"][0]["source"]["adapter"] == "yupoo"
    assert SELF_DECLARED_REPLICA in payload["replica"][0]["why"]["tab_reason"]
    replica_ids = {row["candidate_id"] for row in payload["replica"]}
    real_ids = {row["candidate_id"] for row in payload["real"]}
    possible_ids = {row["candidate_id"] for row in payload["possibly_real"]}
    assert replica.candidate_id in replica_ids
    assert replica.candidate_id not in real_ids
    assert replica.candidate_id not in possible_ids

    filtered = client.get(f"/v1/searches/{search_id}/results?bucket=replica").json()
    assert filtered["bucket"] == "replica"
    assert len(filtered["results"]) == 1

    with client.stream("GET", f"/v1/searches/{search_id}/events") as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = parse_sse(body)
    replica_events = [item for item in events if item["event"] == "result.replica"]
    assert replica_events
    assert replica_events[0]["data"]["bucket"] == "replica"
    assert replica_events[0]["data"]["candidate_id"] == replica.candidate_id
    assert replica_events[0]["data"]["result_id"]
    names = {item["event"] for item in events}
    assert PublicEventName.RESULT_REAL.value in names
    assert PublicEventName.RESULT_POSSIBLY_REAL.value in names
    assert PublicEventName.RESULT_REPLICA.value in names
