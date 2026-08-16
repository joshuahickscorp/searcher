"""Idempotency keys and controller de-duplication."""

from __future__ import annotations

from tests.conftest import make_budget, make_intent

from searcher.campaigns.models import EvidencePacket
from searcher.core.ids import idempotency_key
from searcher.core.policy import POLICY_VERSION


def test_key_is_deterministic() -> None:
    kwargs = dict(
        task_type="normalize",
        search_id="s1",
        input_digests=["abc"],
        adapter_version="a1",
        backend_version="b1",
        policy_version=POLICY_VERSION,
        parameters={"k": 1},
    )
    assert idempotency_key(**kwargs) == idempotency_key(**kwargs)


def test_key_changes_with_input() -> None:
    base = dict(
        task_type="normalize",
        search_id="s1",
        input_digests=["abc"],
        adapter_version="a1",
        backend_version="b1",
        policy_version=POLICY_VERSION,
        parameters={},
    )
    other = dict(base)
    other["input_digests"] = ["abd"]
    assert idempotency_key(**base) != idempotency_key(**other)


def test_controller_does_not_duplicate_task(controller: object) -> None:
    intent = make_intent()
    controller.create(intent, budget=make_budget())  # type: ignore[attr-defined]
    capsule = controller.make_capsule(  # type: ignore[attr-defined]
        intent.search_id, "normalize_listings", input_digests=["d1"], parameters={"n": 1}
    )
    calls = {"n": 0}

    def worker(cap: object) -> EvidencePacket:
        calls["n"] += 1
        return EvidencePacket(
            task_id=cap.task_id,
            search_id=intent.search_id,
            idempotency_key=cap.idempotency_key,
            outputs={"task_type": "normalize_listings"},
        )

    first = controller.run_task(capsule, worker)  # type: ignore[attr-defined]
    second = controller.run_task(capsule, worker)  # type: ignore[attr-defined]
    assert calls["n"] == 1
    assert first.idempotency_key == second.idempotency_key
