"""Receipt verification and tamper detection."""

from __future__ import annotations

import json
from pathlib import Path

from searcher.receipts.base import ReceiptBase
from searcher.receipts.types import CampaignTerminalReceipt, typed_from_payload


def test_seal_and_verify() -> None:
    receipt = ReceiptBase(
        search_id="s1",
        input_digests=["aa"],
        output_digests=["bb"],
        payload={"k": "v"},
    ).seal()
    assert receipt.digest
    assert receipt.verify()


def test_tamper_fails_verification() -> None:
    receipt = CampaignTerminalReceipt(
        search_id="s1",
        terminal_status="COMPLETE",
        terminal_reason="ok",
        state_version=3,
    ).seal()
    assert receipt.verify()
    tampered = receipt.model_copy(update={"terminal_reason": "nope"})
    assert not tampered.verify()


def test_stored_file_tamper(tmp_path: Path) -> None:
    receipt = ReceiptBase(search_id="s1", payload={"n": 1}).seal()
    path = tmp_path / "receipt.json"
    path.write_text(receipt.model_dump_json(), encoding="utf-8")
    loaded = typed_from_payload(json.loads(path.read_text(encoding="utf-8")))
    assert loaded.verify()
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["payload"] = {"n": 2}
    path.write_text(json.dumps(raw), encoding="utf-8")
    broken = typed_from_payload(json.loads(path.read_text(encoding="utf-8")))
    assert not broken.verify()
