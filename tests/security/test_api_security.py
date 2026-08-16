"""Hostile uploads, isolation, CORS, and log hygiene over HTTP."""

from __future__ import annotations

import io
import logging
import struct
from typing import Any

from PIL import Image

from searcher.campaigns.runner import FixtureRunner


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (24, 24), (8, 16, 24)).save(buf, format="PNG")
    return buf.getvalue()


def _post(client: Any, data: bytes, name: str = "x.png", mime: str = "image/png") -> Any:
    return client.post(
        "/v1/searches",
        data={"text": "probe"},
        files=[("images", (name, data, mime))],
    )


def test_bad_magic_is_typed_not_500(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    response = _post(client, b"not-an-image", name="x.png")
    assert response.status_code == 422
    assert response.json()["error"] in {"validation", "malformed_content"}


def test_zero_byte_rejected(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    response = _post(client, b"", name="empty.png")
    assert response.status_code == 422
    assert response.status_code != 500


def test_oversized_rejected(api_app: tuple[Any, Any]) -> None:
    client, app = api_app
    cap = app.state.searcher.settings.max_upload_bytes
    payload = b"\x89PNG\r\n\x1a\n" + b"x" * (cap + 1)
    response = _post(client, payload, name="huge.png")
    assert response.status_code == 422


def test_decompression_bomb_rejected(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    ihdr = struct.pack(">IIBBBBB", 7000, 7000, 8, 2, 0, 0, 0)
    blob = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00\x00\x00\x00"
    response = _post(client, blob, name="bomb.png")
    assert response.status_code == 422
    assert response.status_code != 500


def test_path_traversal_filename_rejected(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    response = _post(client, _png(), name="../../etc/passwd")
    assert response.status_code == 422
    assert response.json()["error"] == "validation"


def test_wrong_extension_uses_magic_not_500(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    accepted = _post(client, _png(), name="notes.txt", mime="text/plain")
    assert accepted.status_code == 201
    exe = _post(client, b"MZ\x90\x00not-an-image", name="photo.png")
    assert exe.status_code == 422


def test_cross_campaign_http_isolation(api_app: tuple[Any, Any]) -> None:
    client, app = api_app
    runner = FixtureRunner(app.state.searcher.controller)
    first = runner.create("dior_minimal")
    runner.run(first.search_id)
    second = runner.create("dior_minimal")
    runner.run(second.search_id)
    a = client.get(f"/v1/searches/{first.search_id}/results").json()
    b = client.get(f"/v1/searches/{second.search_id}/results").json()
    a_ids = {row["result_id"] for row in a["real"] + a["possibly_real"]}
    b_ids = {row["result_id"] for row in b["real"] + b["possibly_real"]}
    assert a_ids
    assert b_ids
    assert a_ids.isdisjoint(b_ids)
    leaked = client.get(f"/v1/searches/{first.search_id}/results").json()
    for row in leaked["real"] + leaked["possibly_real"]:
        assert row["search_id"] == first.search_id
    events_a = client.get(f"/v1/searches/{first.search_id}")
    events_b = client.get(f"/v1/searches/{second.search_id}")
    assert events_a.json()["search_id"] != events_b.json()["search_id"]
    traversal = client.get("/v1/searches/../" + second.search_id)
    assert traversal.status_code in {404, 422}


def test_cors_is_explicit(api_app: tuple[Any, Any]) -> None:
    client, _app = api_app
    allowed = client.options(
        "/v1/health",
        headers={
            "Origin": "http://127.0.0.1:8080",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:8080"
    assert allowed.headers.get("access-control-allow-credentials") in {None, "false"}
    denied = client.get("/v1/health", headers={"Origin": "https://evil.example"})
    assert denied.headers.get("access-control-allow-origin") not in {
        "*",
        "https://evil.example",
    }


def test_logs_omit_filename_and_paths(api_app: tuple[Any, Any], caplog: Any) -> None:
    client, _app = api_app
    caplog.set_level(logging.INFO, logger="searcher.api")
    _post(client, _png(), name="secret-upload.png")
    _post(client, b"", name="/tmp/private/photo.png")
    text = caplog.text
    assert "secret-upload.png" not in text
    assert "/tmp/private" not in text
    assert "photo.png" not in text
