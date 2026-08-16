"""Run a campaign twice over an overlapping query; the second is served from the index."""

from __future__ import annotations

from searcher.campaigns.runner import FixtureRunner


def _cost_receipts(controller: object, search_id: str) -> list[dict[str, object]]:
    rows = controller.repos.list_receipts(search_id)  # type: ignore[attr-defined]
    return [row for row in rows if row.get("receipt_type") == "CostReceipt"]


def _phase(receipts: list[dict[str, object]], phase: str) -> dict[str, object]:
    for row in receipts:
        payload = row.get("payload") or {}
        if isinstance(payload, dict) and payload.get("phase") == phase:
            return row
    raise AssertionError(f"no CostReceipt with phase={phase}: {receipts}")


def test_repeat_overlapping_search_uses_index(controller: object) -> None:
    runner = FixtureRunner(controller)  # type: ignore[arg-type]
    first = runner.create("dior_minimal")
    runner.run(first.search_id)
    second = runner.create("dior_minimal")
    runner.run(second.search_id)

    fetches_1 = len(controller.repos.list_fetch_attempts(first.search_id))  # type: ignore[attr-defined]
    fetches_2 = len(controller.repos.list_fetch_attempts(second.search_id))  # type: ignore[attr-defined]
    assert fetches_1 > 0
    assert fetches_2 == 0
    assert fetches_2 < fetches_1

    first_candidates = controller.repos.list_candidates(first.search_id)  # type: ignore[attr-defined]
    second_candidates = controller.repos.list_candidates(second.search_id)  # type: ignore[attr-defined]
    assert first_candidates
    assert {item.canonical_url for item in second_candidates} == {
        item.canonical_url for item in first_candidates
    }
    for item in second_candidates:
        assert item.last_checked_at is not None

    runtime = controller.repos.get_runtime(second.search_id)  # type: ignore[attr-defined]
    assert runtime.get("index_skip_source_work") is True
    assert int(runtime.get("index_hits") or 0) >= 1

    first_costs = _cost_receipts(controller, first.search_id)
    second_costs = _cost_receipts(controller, second.search_id)
    remember = _phase(first_costs, "remember")
    consult = _phase(second_costs, "consult")
    remember_payload = remember["payload"]
    consult_payload = consult["payload"]
    assert isinstance(remember_payload, dict)
    assert isinstance(consult_payload, dict)
    assert int(remember_payload.get("fetches") or 0) == fetches_1
    assert int(consult["cache_hits"] or 0) >= 1
    assert int(consult_payload.get("fetches") or 0) == 0
    assert int(consult_payload.get("listings_surfaced") or 0) >= 1
    assert int(remember["cache_hits"] or 0) == 0
