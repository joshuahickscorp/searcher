"""A campaign that hides everything says which gate closed.

The note used to read "Some candidates did not meet policy", which a reader
cannot act on, while every hidden result already carried its reason codes. A
search that returns nothing is a legitimate outcome; one that will not say why
is not.
"""

from __future__ import annotations

import json
from typing import Any

from searcher.api.views import _hidden_reason_note


class _Repos:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def list_results(self, _search_id: str) -> list[dict[str, Any]]:
        return self._rows


class _Controller:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.repos = _Repos(rows)


def _row(bucket: str, codes: list[str], *, as_json: bool = False) -> dict[str, Any]:
    payload = {"reason_codes": codes}
    if as_json:
        return {"public_bucket": bucket, "payload_json": json.dumps(payload)}
    return {"public_bucket": bucket, "payload": payload}


def test_the_note_names_the_gates_that_closed() -> None:
    rows = [
        _row("hidden", ["INSUFFICIENT_MATCH", "hidden"]),
        _row("hidden", ["INSUFFICIENT_MATCH", "hidden"]),
        _row("hidden", ["DEAD_LISTING", "hidden"]),
        _row("possibly_real", ["possibly-real-gate"]),
    ]
    note = _hidden_reason_note(_Controller(rows), "s1", 3)  # type: ignore[arg-type]
    assert "the evidence did not establish the same item" in note
    assert "no longer offered" in note
    assert "2 because" in note


def test_a_payload_stored_as_json_is_read() -> None:
    rows = [_row("hidden", ["SELF_DECLARED_REPLICA", "hidden"], as_json=True)]
    note = _hidden_reason_note(_Controller(rows), "s1", 1)  # type: ignore[arg-type]
    assert "replica" in note


def test_without_reason_codes_it_still_states_the_count() -> None:
    rows = [{"public_bucket": "hidden", "payload": {}}]
    note = _hidden_reason_note(_Controller(rows), "s1", 1)  # type: ignore[arg-type]
    assert note == "1 candidate(s) were hidden."
