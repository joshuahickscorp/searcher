"""Process-wide API state. The campaign controller is the only campaign writer."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException, Request

from searcher.campaigns.controller import CampaignController
from searcher.contracts.models import SearchCampaign
from searcher.core.config import Settings
from searcher.evidence.content_store import ContentStore
from searcher.storage.connection import Database
from searcher.storage.migrations import migrate


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.error = error
        self.detail = detail


@dataclass
class AppState:
    settings: Settings
    db: Database
    store: ContentStore
    controller: CampaignController
    threads: dict[str, threading.Thread] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


def build_state(settings: Settings) -> AppState:
    settings.ensure_data_root()
    db = Database(settings.db_path)
    migrate(db, settings.migrations_dir)
    store = ContentStore(
        settings.data_root,
        disk_margin_bytes=settings.disk_margin_bytes,
        max_object_bytes=settings.max_object_bytes,
    )
    controller = CampaignController(db, store, settings)
    return AppState(settings=settings, db=db, store=store, controller=controller)


def get_state(request: Request) -> AppState:
    state = getattr(request.app.state, "searcher", None)
    if not isinstance(state, AppState):
        raise RuntimeError("API state is not initialized")
    return state


def require_campaign(state: AppState, search_id: str) -> SearchCampaign:
    try:
        deleted = state.controller.repos.is_deleted(search_id)
        campaign = state.controller.repos.get_campaign(search_id)
    except KeyError as exc:
        raise ApiError(
            404,
            "search_not_found",
            "This search is no longer available.",
        ) from exc
    if campaign is None or deleted:
        raise ApiError(
            404,
            "search_not_found",
            "This search is no longer available.",
        )
    return campaign


def start_campaign_thread(state: AppState, search_id: str) -> None:
    from searcher.workers.api_campaign import run_api_campaign

    def _run() -> None:
        try:
            run_api_campaign(state.controller, search_id)
        except Exception:
            return

    thread = threading.Thread(target=_run, name=f"campaign-{search_id[:8]}", daemon=True)
    with state.lock:
        state.threads[search_id] = thread
    thread.start()


def wait_for_campaign(state: AppState, search_id: str, timeout: float = 2.0) -> None:
    with state.lock:
        thread = state.threads.get(search_id)
    if thread is not None and thread.is_alive():
        thread.join(timeout)


def find_web_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in [Path.cwd(), *here.parents]:
        candidate = parent / "web"
        if (candidate / "index.html").is_file():
            return candidate
    return None


def http_error(status_code: int, error: str, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": error, "detail": detail})
