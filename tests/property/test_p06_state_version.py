"""Property 6: state_version is monotonic."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given
from hypothesis import strategies as st
from tests.conftest import make_intent

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.models import TransitionContext
from searcher.contracts.enums import CampaignState
from searcher.core.budgets import Budget
from searcher.core.config import Settings
from searcher.evidence.content_store import ContentStore
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate

_HOP = [
    CampaignState.VALIDATING_INPUT,
    CampaignState.INGESTING_REFERENCES,
    CampaignState.CALIBRATING_REFERENCES,
]


@given(st.integers(min_value=1, max_value=3))
def test_state_version_is_monotonic(hops: int) -> None:
    with TemporaryDirectory() as raw:
        settings = Settings.from_env(data_root=Path(raw))
        db = Database(settings.db_path)
        migrate(db)
        controller = CampaignController(db, ContentStore(settings.data_root), settings)
        intent = make_intent()
        campaign = controller.create(intent, budget=Budget.fixture_default())
        versions = [campaign.state_version]
        ctx = TransitionContext(has_query=True, has_visual_representation=True)
        for target in _HOP[:hops]:
            campaign = controller.transition(intent.search_id, target, context=ctx)
            versions.append(campaign.state_version)
        db.close()
        assert versions == sorted(versions)
        assert len(set(versions)) == len(versions)
        assert all(
            later == earlier + 1 for earlier, later in zip(versions, versions[1:], strict=False)
        )
