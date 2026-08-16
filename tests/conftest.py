"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, settings

from searcher.campaigns.controller import CampaignController
from searcher.contracts.models import IntentBudget, PrivacySettings, SearchConstraints, SearchIntent
from searcher.core.budgets import Budget
from searcher.core.config import Settings
from searcher.core.ids import new_id
from searcher.core.time import parse_utc
from searcher.evidence.content_store import ContentStore
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate

settings.register_profile(
    "searcher",
    settings(
        max_examples=60,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    ),
)
settings.load_profile("searcher")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings.from_env(data_root=tmp_path)


@pytest.fixture
def db(settings: Settings) -> Iterator[Database]:
    settings.ensure_data_root()
    database = Database(settings.db_path)
    migrate(database)
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def store(settings: Settings) -> ContentStore:
    return ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )


@pytest.fixture
def controller(db: Database, store: ContentStore, settings: Settings) -> CampaignController:
    return CampaignController(db, store, settings)


@pytest.fixture
def api_app(tmp_path: Path) -> Iterator[tuple[Any, Any]]:
    from fastapi.testclient import TestClient

    from searcher.api.main import create_app

    settings = Settings.from_env(data_root=tmp_path / "api-data")
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, app


def make_intent(search_id: str | None = None) -> SearchIntent:
    return SearchIntent(
        search_id=search_id or new_id(),
        created_at=parse_utc("2007-06-15T12:00:00+00:00"),
        text="Dior Homme General Army Trainer 07",
        tags=["dior"],
        constraints=SearchConstraints(brand="Dior Homme"),
        budget=IntentBudget(
            wall_seconds=60,
            source_limit=4,
            page_limit=20,
            browser_page_limit=0,
            image_limit=10,
            model_call_limit=0,
            byte_limit=1_000_000,
            monetary_limit=None,
        ),
        privacy=PrivacySettings(),
    )


def make_budget() -> Budget:
    return Budget.fixture_default()
