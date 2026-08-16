"""HTTP API: every §26.2 endpoint, happy path and error path."""

from __future__ import annotations

import io
import json
import threading
import time
from typing import Any

from PIL import Image

from searcher.campaigns.runner import FixtureRunner
from searcher.contracts.enums import CampaignState, FeedbackVerdict, PublicEventName

PUBLIC_EVENTS = {item.value for item in PublicEventName}


def _png(color: tuple[int, int, int] = (12, 24, 36)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(buf, format="PNG")
    return buf.getvalue()


def _create(
    client: Any,
    *,
    images: list[bytes] | None = None,
    text: str = "Dior Homme General Army Trainer",
    tags: list[str] | None = None,
    client_search_id: str | None = None,
    field_name: str = "images",
) -> Any:
    files: list[tuple[str, Any]] = [
        (field_name, (f"ref-{index}.png", blob, "image/png"))
        for index, blob in enumerate(images or [_png()])
    ]
    files.append(("text", (None, text)))
    for tag in tags or ["dior"]:
        files.append(("tags", (None, tag)))
    if client_search_id:
        files.append(("client_search_id", (None, client_search_id)))
    return client.post("/v1/searches", files=files)


def wait_terminal(client: Any, search_id: str, timeout: float = 45.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] | None = None
    while time.time() < deadline:
        response = client.get(f"/v1/searches/{search_id}")
        assert response.status_code == 200
        last = response.json()
        if last.get("terminal_status"):
            return last
        time.sleep(0.05)
    raise AssertionError(f"campaign did not reach a terminal verdict: {last}")


def parse_sse(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in text.split("\n\n"):
        if not block.strip() or block.lstrip().startswith(":"):
            continue
        item: dict[str, Any] = {"id": None, "event": None, "data": {}}
        for line in block.splitlines():
            if line.startswith("id:"):
                item["id"] = int(line[3:].strip())
            elif line.startswith("event:"):
                item["event"] = line[6:].strip()
            elif line.startswith("data:"):
                item["data"] = json.loads(line[5:].strip() or "{}")
        if item["event"]:
            events.append(item)
    return events


def read_sse(
    client: Any,
    search_id: str,
    *,
    last_event_id: int | None = None,
    timeout: float = 45.0,
) -> list[dict[str, Any]]:
    headers = {}
    if last_event_id is not None:
        headers["Last-Event-ID"] = str(last_event_id)
    with client.stream(
        "GET", f"/v1/searches/{search_id}/events", headers=headers, timeout=timeout
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    return parse_sse(body)


def test_health_is_cheap_when_warm(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    first = client.get("/v1/health")
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "ok"
    assert body["api"] == "up"
    assert body["db"] == "ok"
    assert "lanes" in body
    assert "blocked_lanes" in body
    assert body["lanes"]["storage"]["ok"] is True
    started = time.perf_counter()
    second = client.get("/v1/health")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert second.status_code == 200
    assert second.json()["status"] == "ok"
    assert elapsed_ms < 100


def test_capabilities_reflect_real_probe(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v1"
    assert body["min_images"] == 1
    assert body["max_images"] == 10
    assert "image/png" in body["accepted_media_types"]
    assert body["discovery"]["available"] is False
    assert body["routing"]["available"] is False
    names = {lane["name"] for lane in body["lanes"]}
    assert "IMAGE_DECODE" in names
    assert any(item["name"] for item in body["blocked_lanes"])


def test_create_returns_immediately(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    started = time.perf_counter()
    response = _create(client, images=[_png(), _png((40, 40, 40))])
    elapsed = time.perf_counter() - started
    assert response.status_code == 201
    body = response.json()
    assert elapsed < 2.0
    assert body["state"] == CampaignState.CREATED.value
    assert body["events_url"] == f"/v1/searches/{body['search_id']}/events"
    assert body["results_url"] == f"/v1/searches/{body['search_id']}/results"
    snapshot = client.get(f"/v1/searches/{body['search_id']}")
    assert snapshot.status_code == 200
    assert snapshot.json()["terminal_status"] in {
        None,
        "BLOCKED",
        "FAILED",
        "CANCELLED",
    }


def test_images_bracket_name_accepted(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    response = _create(client, field_name="images[]")
    assert response.status_code == 201


def test_create_validation_errors(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    missing = client.post(
        "/v1/searches",
        data={"text": "x"},
        files=[("notes", ("a.txt", b"hello", "text/plain"))],
    )
    assert missing.status_code == 422
    assert missing.json()["error"] == "validation"
    too_many = _create(client, images=[_png()] * 11)
    assert too_many.status_code == 422
    json_body = client.post("/v1/searches", json={"text": "nope"})
    assert json_body.status_code == 415
    unknown = client.get("/v1/searches/not-a-real-id")
    assert unknown.status_code == 404
    assert unknown.json()["error"] == "search_not_found"


def test_client_search_id_is_idempotent(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    first = _create(client, client_search_id="same-client-key")
    second = _create(client, client_search_id="same-client-key")
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["search_id"] == second.json()["search_id"]


def test_campaign_runs_to_honest_blocked(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    created = _create(client)
    search_id = created.json()["search_id"]
    terminal = wait_terminal(client, search_id)
    assert terminal["terminal_status"] == "BLOCKED"
    assert terminal["state"] == "BLOCKED"
    reason = (terminal["terminal_reason"] or "").lower()
    assert "not a finding that the item does not exist" in reason
    assert terminal["coverage"]["sources_blocked"]
    results = client.get(f"/v1/searches/{search_id}/results")
    assert results.status_code == 200
    payload = results.json()
    assert payload["real"] == []
    assert payload["possibly_real"] == []
    assert payload["counts"]["real"] == 0
    real_only = client.get(f"/v1/searches/{search_id}/results?bucket=real")
    assert real_only.json()["bucket"] == "real"
    assert real_only.json()["results"] == []
    bad = client.get(f"/v1/searches/{search_id}/results?bucket=hidden")
    assert bad.status_code == 400


def test_sse_public_names_and_reconnect(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    search_id = _create(client).json()["search_id"]
    events = read_sse(client, search_id)
    names = [item["event"] for item in events]
    assert names
    assert set(names) <= PUBLIC_EVENTS
    assert "search.state" in names
    assert "search.progress" in names
    assert "search.complete" in names
    ids = [item["id"] for item in events]
    assert ids == list(range(1, len(ids) + 1))
    complete = [item for item in events if item["event"] == "search.complete"]
    assert complete[-1]["data"]["terminal_status"] == "BLOCKED"
    progress = [item for item in events if item["event"] == "search.progress"]
    assert progress[0]["data"]["stage"]
    replayed = read_sse(client, search_id, last_event_id=ids[0])
    replay_ids = [item["id"] for item in replayed]
    assert ids[0] not in replay_ids
    assert replay_ids == ids[1:]
    full = read_sse(client, search_id, last_event_id=0)
    assert [item["id"] for item in full] == ids


def test_cancel_mid_campaign(api_app: tuple[Any, Any], monkeypatch: Any) -> None:
    client, _app = api_app
    started = threading.Event()
    release = threading.Event()

    def _hold(
        controller: Any, search_id: str, image_paths: Any, **kwargs: Any
    ) -> dict[str, object]:
        del image_paths, kwargs
        started.set()
        release.wait(timeout=15)
        controller.cancellation.raise_if_cancelled(search_id)
        return {}

    monkeypatch.setattr("searcher.workers.api_campaign.run_reference_query_wave", _hold)
    search_id = _create(client).json()["search_id"]
    assert started.wait(timeout=5)
    cancelled = client.post(f"/v1/searches/{search_id}/cancel")
    assert cancelled.status_code == 200
    release.set()
    body = cancelled.json()
    terminal = wait_terminal(client, search_id)
    assert terminal["terminal_status"] == "CANCELLED"
    assert body["terminal_status"] == "CANCELLED"


def test_refresh_feedback_delete(api_app: tuple[Any, Any]) -> None:
    client, app = api_app
    search_id = _create(client).json()["search_id"]
    wait_terminal(client, search_id)
    refresh = client.post(f"/v1/searches/{search_id}/refresh")
    assert refresh.status_code == 202
    assert refresh.json()["refreshed"] is False
    missing = client.post(
        "/v1/results/no-such/feedback",
        json={"verdict": FeedbackVerdict.USEFUL_RESULT.value},
    )
    assert missing.status_code == 404
    runner = FixtureRunner(app.state.searcher.controller)
    intent = runner.create("dior_minimal")
    runner.run(intent.search_id)
    listed = client.get(f"/v1/searches/{intent.search_id}/results")
    assert listed.status_code == 200
    real = listed.json()["real"]
    possible = listed.json()["possibly_real"]
    assert real
    assert possible
    detail = client.get(f"/v1/results/{real[0]['result_id']}")
    assert detail.status_code == 200
    card = detail.json()
    assert card["item_match"]["label"]
    assert card["authenticity"]["label"]
    assert "live" in card["listing_utility"]
    assert card["why"]["heading"]
    feedback = client.post(
        f"/v1/results/{real[0]['result_id']}/feedback",
        json={"verdict": "correct_item"},
    )
    assert feedback.status_code == 202
    assert feedback.json()["ok"] is True
    assert feedback.json()["applied"] is False
    after = client.get(f"/v1/searches/{intent.search_id}/results")
    assert [row["result_id"] for row in after.json()["real"]] == [row["result_id"] for row in real]
    deleted = client.delete(f"/v1/searches/{intent.search_id}")
    assert deleted.status_code == 204
    assert client.get(f"/v1/searches/{intent.search_id}").status_code == 404
    assert client.get(f"/v1/results/{real[0]['result_id']}").status_code == 404
    receipts = app.state.searcher.controller.repos.list_receipts(intent.search_id)
    types = {row["receipt_type"] for row in receipts}
    assert "DeletionReceipt" in types


def test_unknown_result_and_bucket(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    assert client.get("/v1/results/missing").status_code == 404
    created = _create(client)
    wait_terminal(client, created.json()["search_id"])
    bad = client.post(
        "/v1/results/missing/feedback",
        json={"verdict": "not-a-verdict"},
    )
    assert bad.status_code == 422
