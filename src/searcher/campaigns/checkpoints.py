"""§10.3 checkpoint points."""

from __future__ import annotations

from searcher.campaigns.models import Checkpoint
from searcher.campaigns.states import CHECKPOINT_AFTER
from searcher.contracts.enums import CampaignState
from searcher.core.ids import new_id
from searcher.core.time import format_utc, utc_now
from searcher.storage.repositories import Repositories


def checkpoint_label_for(state: CampaignState) -> str | None:
    return CHECKPOINT_AFTER.get(state)


def write_checkpoint(
    repos: Repositories,
    *,
    search_id: str,
    state: CampaignState,
    state_version: int,
    label: str,
    payload: dict[str, object] | None = None,
    receipt_ref: str | None = None,
) -> Checkpoint:
    created = utc_now()
    record = Checkpoint(
        checkpoint_id=new_id(),
        search_id=search_id,
        state=state,
        state_version=state_version,
        label=label,
        created_at=created,
        receipt_ref=receipt_ref,
        payload=payload or {},
    )
    stored = record.model_dump(mode="json")
    stored["created_at"] = format_utc(created)
    repos.insert_checkpoint(stored)
    return record
