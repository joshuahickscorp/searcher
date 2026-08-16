"""Property 4: a repeated task with the same key does not duplicate work."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given
from hypothesis import strategies as st
from tests.conftest import make_intent

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.models import EvidencePacket
from searcher.core.budgets import Budget
from searcher.core.config import Settings
from searcher.evidence.content_store import ContentStore
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate


@given(st.text(min_size=1, max_size=12), st.integers(min_value=0, max_value=5))
def test_repeated_task_same_key_does_not_duplicate_work(label: str, extra_repeats: int) -> None:
    with TemporaryDirectory() as raw:
        root = Path(raw)
        settings = Settings.from_env(data_root=root)
        db = Database(settings.db_path)
        migrate(db)
        store = ContentStore(settings.data_root)
        controller = CampaignController(db, store, settings)
        intent = make_intent()
        controller.create(intent, budget=Budget.fixture_default())
        capsule = controller.make_capsule(
            intent.search_id,
            "normalize_listings",
            input_digests=[label],
            parameters={"label": label},
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

        controller.run_task(capsule, worker)
        for _ in range(extra_repeats):
            controller.run_task(capsule, worker)
        db.close()
        assert calls["n"] == 1
