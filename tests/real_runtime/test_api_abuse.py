"""Hostile and clumsy input against a real loopback API process."""

from __future__ import annotations

import io
import json
import struct
import threading
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image
from tests.support.live_api import LiveApi, live_api, parse_sse, wait_terminal

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "artifacts" / "hardening" / "abuse-table.json"


def _png(color: tuple[int, int, int] = (12, 24, 36), size: int = 24) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="PNG")
    return buf.getvalue()


def _lying_png() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + ihdr
        + b"\x00\x00\x00\x00"
        + b"not-a-real-idat-payload"
    )


def _bomb_png() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 7000, 7000, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00\x00\x00\x00"


def _create(
    client: httpx.Client,
    *,
    images: list[tuple[bytes, str]] | None = None,
    text: str = "Dior Homme General Army Trainer",
    tags: list[str] | None = None,
    client_search_id: str | None = None,
) -> httpx.Response:
    files: list[tuple[str, Any]] = [
        ("images", (name, blob, "image/png"))
        for blob, name in (images or [(_png(), "ref.png")])
    ]
    files.append(("text", (None, text)))
    for tag in tags if tags is not None else ["dior"]:
        files.append(("tags", (None, tag)))
    if client_search_id is not None:
        files.append(("client_search_id", (None, client_search_id)))
    return client.post("/v1/searches", files=files)


def _record(rows: list[dict[str, object]], **row: object) -> None:
    rows.append(row)


@pytest.fixture(scope="module")
def api(tmp_path_factory: pytest.TempPathFactory) -> Iterator[LiveApi]:
    root = tmp_path_factory.mktemp("abuse-api")
    with live_api(root) as server:
        yield server


@pytest.fixture(scope="module")
def client(api: LiveApi) -> Iterator[httpx.Client]:
    with api.client(timeout=20.0) as held:
        yield held


@pytest.fixture(scope="module")
def abuse_rows() -> Iterator[list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    yield rows
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    TABLE.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")


def test_zero_images(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = client.post(
        "/v1/searches",
        files=[("text", (None, "no image")), ("tags", (None, "dior"))],
    )
    _record(
        abuse_rows,
        case="zero_images",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation"


def test_eleven_images(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    images = [(_png((i, i, i)), f"n{i}.png") for i in range(11)]
    response = _create(client, images=images)
    _record(
        abuse_rows,
        case="eleven_images",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation"


def test_twenty_five_mb_image(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    blob = b"\x89PNG\r\n\x1a\n" + b"x" * (25 * 1024 * 1024)
    response = _create(client, images=[(blob, "huge.png")])
    body = response.json()
    _record(
        abuse_rows,
        case="25mb_image",
        status=response.status_code,
        error=body.get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert body["error"] == "validation"
    assert "/Users" not in response.text
    assert "/tmp" not in response.text


def test_not_an_image(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(client, images=[(b"not-an-image", "x.png")])
    _record(
        abuse_rows,
        case="not_an_image",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "malformed_content"


def test_lying_png_header(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(client, images=[(_lying_png(), "lie.png")])
    # Header-only validation may accept it; decode then stops the campaign honestly.
    if response.status_code == 201:
        search_id = response.json()["search_id"]
        terminal = wait_terminal(client, search_id)
        _record(
            abuse_rows,
            case="lying_png_header",
            status=response.status_code,
            error=terminal.get("terminal_status"),
            honest=terminal["terminal_status"] in {"BLOCKED", "FAILED"},
        )
        assert terminal["terminal_status"] == "BLOCKED"
        assert terminal["terminal_reason"]
    else:
        _record(
            abuse_rows,
            case="lying_png_header",
            status=response.status_code,
            error=response.json().get("error"),
            honest=response.status_code == 422,
        )
        assert response.status_code == 422
        assert response.json()["error"] in {"validation", "malformed_content"}


def test_zip_renamed_jpg(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(client, images=[(b"PK\x03\x04payload", "photo.jpg")])
    _record(
        abuse_rows,
        case="zip_renamed_jpg",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation"


def test_decompression_bomb(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(client, images=[(_bomb_png(), "bomb.png")])
    _record(
        abuse_rows,
        case="decompression_bomb",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "malformed_content"


def test_svg_rejected(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(
        client,
        images=[(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "x.svg")],
    )
    _record(
        abuse_rows,
        case="svg",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation"


def test_zero_byte_file(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(client, images=[(b"", "empty.png")])
    _record(
        abuse_rows,
        case="zero_byte",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "malformed_content"


def test_duplicate_filenames(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(
        client,
        images=[(_png((1, 2, 3)), "same.png"), (_png((4, 5, 6)), "same.png")],
    )
    _record(
        abuse_rows,
        case="duplicate_filenames",
        status=response.status_code,
        error=response.json().get("error") if response.status_code >= 400 else None,
        honest=response.status_code == 201,
    )
    assert response.status_code == 201
    wait_terminal(client, response.json()["search_id"])


def test_hundred_kb_text(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(client, text="x" * (100 * 1024))
    body = response.json()
    _record(
        abuse_rows,
        case="100kb_text",
        status=response.status_code,
        error=body.get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert body["error"] == "validation"


def test_five_hundred_tags(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(client, tags=[f"tag{i}" for i in range(500)])
    _record(
        abuse_rows,
        case="500_tags",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation"


def test_control_and_nul(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    nul = _create(client, text="bad\x00name")
    ctrl = _create(client, tags=["ok", "x\x01y"])
    _record(
        abuse_rows,
        case="nul_byte_text",
        status=nul.status_code,
        error=nul.json().get("error"),
        honest=nul.status_code == 422,
    )
    _record(
        abuse_rows,
        case="control_char_tag",
        status=ctrl.status_code,
        error=ctrl.json().get("error"),
        honest=ctrl.status_code == 422,
    )
    assert nul.status_code == 422
    assert nul.json()["error"] == "validation"
    assert ctrl.status_code == 422
    assert ctrl.json()["error"] == "validation"


def test_rtl_override(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(client, tags=["di\u202eor"])
    _record(
        abuse_rows,
        case="rtl_override_tag",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation"


def test_ten_thousand_char_tag(client: httpx.Client, abuse_rows: list[dict[str, object]]) -> None:
    response = _create(client, tags=["z" * 10_000])
    _record(
        abuse_rows,
        case="10000_char_tag",
        status=response.status_code,
        error=response.json().get("error"),
        honest=response.status_code == 422,
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation"


def test_client_search_id_not_uuid(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    response = _create(client, client_search_id="not-a-uuid-key")
    _record(
        abuse_rows,
        case="client_search_id_not_uuid",
        status=response.status_code,
        error=response.json().get("error") if response.status_code >= 400 else None,
        honest=response.status_code == 201,
    )
    # client_search_id is an idempotency key, not a UUID. Honest accept.
    assert response.status_code == 201
    uuid.UUID(response.json()["search_id"])


def test_path_traversal_identifiers(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    traversal = "../../etc/passwd"
    search = client.get(f"/v1/searches/{traversal}")
    result = client.get(f"/v1/results/{traversal}")
    named = _create(client, images=[(_png(), traversal)])
    _record(
        abuse_rows,
        case="search_id_path_traversal",
        status=search.status_code,
        error=search.json().get("error"),
        honest=search.status_code in {404, 422},
    )
    _record(
        abuse_rows,
        case="result_id_path_traversal",
        status=result.status_code,
        error=result.json().get("error"),
        honest=result.status_code == 404,
    )
    _record(
        abuse_rows,
        case="filename_path_traversal",
        status=named.status_code,
        error=named.json().get("error"),
        honest=named.status_code == 422,
    )
    assert search.status_code in {404, 422}
    assert search.json()["error"] in {"search_not_found", "validation", "not_found"}
    assert result.status_code == 404
    assert result.json()["error"] in {"result_not_found", "not_found"}
    assert named.status_code == 422
    assert named.json()["error"] == "validation"
    assert "/etc/passwd" not in search.text or search.status_code != 200


def test_unknown_and_deleted_search(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    unknown = str(uuid.uuid4())
    missing = client.get(f"/v1/searches/{unknown}")
    created = _create(client)
    search_id = created.json()["search_id"]
    wait_terminal(client, search_id)
    deleted = client.delete(f"/v1/searches/{search_id}")
    after = client.get(f"/v1/searches/{search_id}")
    _record(
        abuse_rows,
        case="unknown_uuid_search",
        status=missing.status_code,
        error=missing.json().get("error"),
        honest=missing.status_code == 404,
    )
    _record(
        abuse_rows,
        case="deleted_search",
        status=after.status_code,
        error=after.json().get("error"),
        honest=after.status_code == 404,
    )
    assert missing.status_code == 404
    assert missing.json()["error"] == "search_not_found"
    assert deleted.status_code == 204
    assert after.status_code == 404
    assert after.json()["error"] == "search_not_found"


def test_last_event_id_variants(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    search_id = _create(client).json()["search_id"]
    wait_terminal(client, search_id)
    for label, header in (
        ("negative", "-1"),
        ("huge", "999999999999"),
        ("non_number", "nope"),
    ):
        response = client.get(
            f"/v1/searches/{search_id}/events",
            headers={"Last-Event-ID": header},
            timeout=10.0,
        )
        _record(
            abuse_rows,
            case=f"last_event_id_{label}",
            status=response.status_code,
            error=None if response.status_code == 200 else response.text[:80],
            honest=response.status_code == 200,
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        events = parse_sse(response.text)
        if label == "huge":
            assert events == []
        else:
            assert any(item["event"] == "search.complete" for item in events)


def test_ten_concurrent_searches(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    def _one(_: int) -> str:
        response = _create(client)
        assert response.status_code == 201
        search_id = response.json()["search_id"]
        terminal = wait_terminal(client, search_id)
        assert terminal["terminal_status"] == "BLOCKED"
        return search_id

    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(_one, i) for i in range(10)]
        ids = [fut.result() for fut in as_completed(futs)]
    _record(
        abuse_rows,
        case="ten_concurrent_searches",
        status=201,
        error=None,
        honest=len(set(ids)) == 10,
    )
    assert len(set(ids)) == 10


def test_sse_client_disappears(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    search_id = _create(client).json()["search_id"]
    with client.stream("GET", f"/v1/searches/{search_id}/events", timeout=2.0) as stream:
        assert stream.status_code == 200
        next(stream.iter_text(), None)
    terminal = wait_terminal(client, search_id)
    _record(
        abuse_rows,
        case="sse_client_disappears",
        status=200,
        error=terminal["terminal_status"],
        honest=terminal["terminal_status"] == "BLOCKED",
    )
    assert terminal["terminal_status"] == "BLOCKED"


def test_twenty_sse_readers(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    search_id = _create(client).json()["search_id"]
    wait_terminal(client, search_id)

    def _read(_: int) -> list[str]:
        response = client.get(f"/v1/searches/{search_id}/events", timeout=15.0)
        assert response.status_code == 200
        return [item["event"] for item in parse_sse(response.text)]

    with ThreadPoolExecutor(max_workers=20) as pool:
        names = [fut.result() for fut in as_completed(pool.submit(_read, i) for i in range(20))]
    _record(
        abuse_rows,
        case="twenty_sse_readers",
        status=200,
        error=None,
        honest=all("search.complete" in row for row in names),
    )
    assert all("search.complete" in row for row in names)


def test_cancel_during_stages(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    early = _create(client)
    early_id = early.json()["search_id"]
    cancelled = client.post(f"/v1/searches/{early_id}/cancel")
    _record(
        abuse_rows,
        case="cancel_early",
        status=cancelled.status_code,
        error=cancelled.json().get("terminal_status"),
        honest=cancelled.status_code == 200,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["terminal_status"] in {"CANCELLED", "BLOCKED"}

    mid = _create(client)
    mid_id = mid.json()["search_id"]
    with client.stream("GET", f"/v1/searches/{mid_id}/events", timeout=5.0) as stream:
        assert stream.status_code == 200
        next(stream.iter_text(), None)
        mid_cancel = client.post(f"/v1/searches/{mid_id}/cancel")
    _record(
        abuse_rows,
        case="cancel_after_first_event",
        status=mid_cancel.status_code,
        error=mid_cancel.json().get("terminal_status"),
        honest=mid_cancel.status_code == 200,
    )
    assert mid_cancel.status_code == 200
    assert mid_cancel.json()["terminal_status"] in {"CANCELLED", "BLOCKED"}

    done = _create(client)
    done_id = done.json()["search_id"]
    wait_terminal(client, done_id)
    late = client.post(f"/v1/searches/{done_id}/cancel")
    _record(
        abuse_rows,
        case="cancel_after_terminal",
        status=late.status_code,
        error=late.json().get("terminal_status"),
        honest=late.status_code == 200,
    )
    assert late.status_code == 200
    assert late.json()["terminal_status"] in {"BLOCKED", "CANCELLED"}


def test_delete_during_stream(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    search_id = _create(client).json()["search_id"]
    status_holder: list[int] = []

    def _stream() -> None:
        try:
            with client.stream(
                "GET", f"/v1/searches/{search_id}/events", timeout=10.0
            ) as stream:
                status_holder.append(stream.status_code)
                for _chunk in stream.iter_text():
                    pass
        except httpx.HTTPError:
            status_holder.append(0)

    reader = threading.Thread(target=_stream)
    reader.start()
    deleted = client.delete(f"/v1/searches/{search_id}")
    reader.join(timeout=10)
    after = client.get(f"/v1/searches/{search_id}")
    _record(
        abuse_rows,
        case="delete_during_stream",
        status=deleted.status_code,
        error=after.json().get("error") if after.status_code != 204 else None,
        honest=deleted.status_code == 204 and after.status_code == 404,
    )
    assert deleted.status_code == 204
    assert after.status_code == 404
    assert after.json()["error"] == "search_not_found"


def test_refresh_terminal_repeatedly(
    client: httpx.Client, abuse_rows: list[dict[str, object]]
) -> None:
    search_id = _create(client).json()["search_id"]
    wait_terminal(client, search_id)
    codes: list[int] = []
    for _ in range(5):
        response = client.post(f"/v1/searches/{search_id}/refresh")
        codes.append(response.status_code)
        assert response.status_code == 202
        assert response.json()["refreshed"] is False
    _record(
        abuse_rows,
        case="refresh_terminal_repeatedly",
        status=202,
        error=None,
        honest=codes == [202] * 5,
    )


def test_disk_margin_and_caps_enforced(
    tmp_path: Path, abuse_rows: list[dict[str, object]]
) -> None:
    import shutil

    padded = _png() + b"\x00" * 700
    caps = {
        "SEARCHER_MAX_OBJECT_BYTES": "800",
        "SEARCHER_MAX_UPLOAD_BYTES": "800",
        "SEARCHER_MAX_TOTAL_UPLOAD_BYTES": "1200",
    }
    with live_api(tmp_path / "caps", extra_env=caps) as server, server.client() as tight:
        over_object = _create(tight, images=[(padded, "cap.png")])
        two = _create(
            tight,
            images=[(_png() + b"\x00" * 500, "a.png"), (_png() + b"\x00" * 500, "b.png")],
        )
        _record(
            abuse_rows,
            case="per_object_cap",
            status=over_object.status_code,
            error=over_object.json().get("error"),
            honest=over_object.status_code == 422,
        )
        _record(
            abuse_rows,
            case="per_search_byte_budget",
            status=two.status_code,
            error=two.json().get("error"),
            honest=two.status_code == 422,
        )
        assert over_object.status_code == 422
        assert over_object.json()["error"] == "validation"
        assert two.status_code == 422
        assert two.json()["error"] == "validation"
        assert "/Users" not in over_object.text

    free = shutil.disk_usage(tmp_path).free
    with live_api(
        tmp_path / "disk",
        extra_env={"SEARCHER_DISK_MARGIN_BYTES": str(free + 1024 * 1024)},
    ) as server, server.client() as tight:
        response = _create(tight)
        _record(
            abuse_rows,
            case="disk_margin",
            status=response.status_code,
            error=response.json().get("error"),
            honest=response.status_code == 422,
        )
        assert response.status_code == 422
        assert response.json()["error"] == "validation"
        assert "/Users" not in response.text
