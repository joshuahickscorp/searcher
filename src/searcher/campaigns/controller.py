"""Single writer of campaign state. Workers return immutable packets."""

from __future__ import annotations

import sqlite3
from typing import Any

from searcher.campaigns.cancellation import CancellationController
from searcher.campaigns.checkpoints import write_checkpoint
from searcher.campaigns.events import CampaignEvent, append_event
from searcher.campaigns.models import (
    Checkpoint,
    EvidencePacket,
    TransitionContext,
    WorkCapsule,
)
from searcher.campaigns.states import is_terminal, terminal_verdict_for
from searcher.campaigns.transitions import assert_invariants, assert_legal
from searcher.contracts.enums import CampaignState, PublicEventName, TaskStatus
from searcher.contracts.models import SearchCampaign, SearchIntent
from searcher.core.budgets import Budget, BudgetUsage, SealedBudget
from searcher.core.config import Settings
from searcher.core.errors import IdempotencyConflict
from searcher.core.ids import idempotency_key, new_id
from searcher.core.time import format_utc, utc_now
from searcher.evidence.content_store import ContentStore
from searcher.evidence.records import EvidenceRecord
from searcher.receipts.base import ReceiptBase
from searcher.receipts.types import DeletionReceipt
from searcher.storage.connection import Database
from searcher.storage.repositories import Repositories


class CampaignController:
    """The only component that commits campaign state transitions."""

    def __init__(
        self,
        db: Database,
        store: ContentStore,
        settings: Settings,
        *,
        cancellation: CancellationController | None = None,
    ) -> None:
        self.db = db
        self.store = store
        self.settings = settings
        self.repos = Repositories(db)
        self.cancellation = cancellation or CancellationController()
        self._usages: dict[str, BudgetUsage] = {}

    def create(
        self,
        intent: SearchIntent,
        *,
        fixture_name: str | None = None,
        budget: Budget | None = None,
        client_search_id: str | None = None,
    ) -> SearchCampaign:
        declared = budget or Budget(
            wall_seconds=intent.budget.wall_seconds,
            source_limit=intent.budget.source_limit,
            page_limit=intent.budget.page_limit,
            browser_page_limit=intent.budget.browser_page_limit,
            image_limit=intent.budget.image_limit,
            model_call_limit=intent.budget.model_call_limit,
            byte_limit=intent.budget.byte_limit,
            monetary_limit=intent.budget.monetary_limit,
        )
        sealed = declared.seal()
        usage = BudgetUsage(sealed, search_id=intent.search_id)
        campaign = SearchCampaign(
            search_id=intent.search_id,
            state=CampaignState.CREATED,
            state_version=0,
            intent_ref=intent.search_id,
            budget_used=usage.snapshot(),
            coverage={},
            fixture_name=fixture_name,
        )
        try:
            self.repos.insert_campaign(
                campaign,
                intent=intent,
                budget=sealed.to_dict(),
                runtime={"completed_steps": [], "pending_comparisons": []},
                client_search_id=client_search_id,
            )
        except sqlite3.IntegrityError:
            if client_search_id:
                existing_id = self.repos.find_search_id_by_client(client_search_id)
                if existing_id:
                    return self.get(existing_id)
            raise
        self.repos.upsert_budget_usage(intent.search_id, usage.snapshot())
        self._usages[intent.search_id] = usage
        self._emit(
            intent.search_id,
            PublicEventName.SEARCH_STATE.value,
            actor="controller",
            state_version=0,
            payload={"state": CampaignState.CREATED.value},
        )
        return campaign

    def get(self, search_id: str) -> SearchCampaign:
        campaign = self.repos.get_campaign(search_id)
        if campaign is None:
            raise KeyError(search_id)
        return campaign

    def usage(self, search_id: str) -> BudgetUsage:
        held = self._usages.get(search_id)
        if held is not None:
            return held
        sealed = SealedBudget.from_dict(self.repos.get_budget_payload(search_id))
        usage = BudgetUsage(sealed, search_id=search_id)
        stored = self.repos.get_budget_usage(search_id)
        if stored:
            usage.restore(stored)
        self._usages[search_id] = usage
        return usage

    def persist_usage(self, search_id: str) -> None:
        usage = self.usage(search_id)
        self.repos.upsert_budget_usage(search_id, usage.snapshot())

    def context_from_disk(self, search_id: str) -> TransitionContext:
        campaign = self.get(search_id)
        runtime = self.repos.get_runtime(search_id)
        queries = self.repos.list_queries(search_id)
        candidates = self.repos.list_candidates(search_id)
        evidence = self.repos.list_evidence(search_id, accepted_only=True)
        has_visual = bool(runtime.get("has_visual_representation"))
        return TransitionContext(
            has_query=len(queries) > 0,
            has_visual_representation=has_visual,
            normalized_candidate_count=len(candidates),
            has_visual_or_normalized_evidence=bool(candidates) or bool(evidence) or has_visual,
            seller_text_only=bool(runtime.get("seller_text_only", False)),
            exhaustion_receipt=campaign.search_exhaustion_receipt
            or runtime.get("exhaustion_receipt"),
            saturation_receipt=runtime.get("saturation_receipt"),
            error_class=None,
            reason="",
        )

    def transition(
        self,
        search_id: str,
        target: CampaignState,
        *,
        context: TransitionContext | None = None,
        actor: str = "controller",
    ) -> SearchCampaign:
        if target is not CampaignState.CANCELLED:
            self.cancellation.raise_if_cancelled(search_id)
        campaign = self.get(search_id)
        ctx = context or self.context_from_disk(search_id)
        assert_legal(campaign.state, target, search_id=search_id)
        assert_invariants(campaign.state, target, ctx, search_id=search_id)
        expected = campaign.state_version
        campaign.state = target
        verdict = terminal_verdict_for(target)
        if verdict is not None:
            campaign.terminal_status = verdict
            campaign.terminal_reason = ctx.reason or campaign.terminal_reason
        if ctx.exhaustion_receipt:
            campaign.search_exhaustion_receipt = ctx.exhaustion_receipt
        campaign.budget_used = self.usage(search_id).snapshot()
        new_version = self.repos.update_campaign_blob(campaign, expected_version=expected)
        campaign.state_version = new_version
        self._emit(
            search_id,
            PublicEventName.SEARCH_STATE.value,
            actor=actor,
            state_version=new_version,
            payload={"state": target.value, "from_version": expected},
        )
        return campaign

    def checkpoint(
        self,
        search_id: str,
        label: str,
        payload: dict[str, object] | None = None,
    ) -> Checkpoint:
        campaign = self.get(search_id)
        record = write_checkpoint(
            self.repos,
            search_id=search_id,
            state=campaign.state,
            state_version=campaign.state_version,
            label=label,
            payload=payload,
        )
        runtime = self.repos.get_runtime(search_id)
        steps = list(runtime.get("completed_steps") or [])
        if campaign.state.value not in steps:
            steps.append(campaign.state.value)
        runtime["completed_steps"] = steps
        runtime["last_checkpoint_id"] = record.checkpoint_id
        self.repos.update_runtime(search_id, runtime)
        return record

    def record_evidence(self, record: EvidenceRecord) -> None:
        self.repos.insert_evidence(record)

    def commit_packet(self, packet: EvidencePacket) -> EvidencePacket:
        """Idempotent commit of a worker packet. Duplicate keys do not re-run."""
        existing = self.repos.get_task_by_key(packet.search_id, packet.idempotency_key)
        if existing is not None:
            return packet
        for evidence in packet.evidence:
            self.repos.insert_evidence(evidence)
        self.repos.insert_task(
            packet.search_id,
            packet.task_id,
            task_type=str(packet.outputs.get("task_type") or "packet"),
            idempotency_key=packet.idempotency_key,
            status=TaskStatus.COMPLETED,
            input_digests=[],
            output_digests=packet.output_digests,
            adapter_version="fixture-1",
            backend_version="none",
            policy_version=self.settings.policy_version,
            parameters={},
            payload=packet.model_dump(mode="json"),
        )
        return packet

    def run_task(self, capsule: WorkCapsule, worker: Any) -> EvidencePacket:
        """Execute worker only if the idempotency key is new.

        GUARD: a repeated task with the same key does not duplicate work.
        """
        existing = self.repos.get_task_by_key(capsule.search_id, capsule.idempotency_key)
        if existing is not None:
            payload = existing.get("payload_json")
            if payload:
                import json

                body = json.loads(payload)
                if "evidence" in body:
                    return EvidencePacket.model_validate(body)
            return EvidencePacket(
                task_id=str(existing["task_id"]),
                search_id=capsule.search_id,
                idempotency_key=capsule.idempotency_key,
                output_digests=[],
                outputs={"reused": True, "task_type": capsule.task_type},
            )
        result = worker(capsule)
        if not isinstance(result, EvidencePacket):
            raise IdempotencyConflict(
                "worker did not return an EvidencePacket",
                search_id=capsule.search_id,
                key=capsule.idempotency_key,
            )
        if result.idempotency_key != capsule.idempotency_key:
            raise IdempotencyConflict(
                "worker returned a different idempotency key",
                search_id=capsule.search_id,
                key=capsule.idempotency_key,
            )
        self.commit_packet(result)
        return result

    def make_capsule(
        self,
        search_id: str,
        task_type: str,
        *,
        input_digests: list[str],
        parameters: dict[str, object] | None = None,
        adapter_version: str = "fixture-1",
        backend_version: str = "none",
    ) -> WorkCapsule:
        params = parameters or {}
        key = idempotency_key(
            task_type=task_type,
            search_id=search_id,
            input_digests=input_digests,
            adapter_version=adapter_version,
            backend_version=backend_version,
            policy_version=self.settings.policy_version,
            parameters=params,
        )
        return WorkCapsule(
            task_id=new_id(),
            search_id=search_id,
            task_type=task_type,
            input_digests=input_digests,
            adapter_version=adapter_version,
            backend_version=backend_version,
            policy_version=self.settings.policy_version,
            parameters=params,
            idempotency_key=key,
        )

    def store_receipt(self, receipt: ReceiptBase) -> ReceiptBase:
        sealed = receipt if receipt.digest else receipt.seal()
        sealed.verify_or_raise()
        self.repos.insert_receipt(sealed.model_dump(mode="json"))
        return sealed

    def cancel(self, search_id: str, *, cleanup_seconds: float = 0.2) -> SearchCampaign:
        self.cancellation.request(search_id)
        self.cancellation.bounded_cleanup(cleanup_seconds)
        campaign = self.get(search_id)
        if campaign.state is CampaignState.CANCELLED:
            return campaign
        ctx = self.context_from_disk(search_id)
        ctx.reason = "cancelled by operator"
        # Cancellation is legal from any non-terminal state via the graph.
        if campaign.state in {
            CampaignState.COMPLETE,
            CampaignState.PARTIAL,
            CampaignState.BLOCKED,
            CampaignState.FAILED,
            CampaignState.CANCELLED,
        }:
            return campaign
        updated = self.transition(search_id, CampaignState.CANCELLED, context=ctx, actor="cancel")
        self.repos.update_open_tasks(search_id, TaskStatus.CANCELLED)
        self.checkpoint(search_id, "terminal", {"reason": "cancelled"})
        self._emit(
            search_id,
            PublicEventName.SEARCH_COMPLETE.value,
            actor="cancel",
            state_version=updated.state_version,
            payload={
                "terminal_status": CampaignState.CANCELLED.value,
                "reason": updated.terminal_reason or "cancelled by operator",
            },
        )
        return updated

    def find_by_client_search_id(self, client_search_id: str) -> SearchCampaign | None:
        search_id = self.repos.find_search_id_by_client(client_search_id)
        if search_id is None:
            return None
        if self.repos.is_deleted(search_id):
            return None
        return self.get(search_id)

    def delete(self, search_id: str) -> DeletionReceipt:
        if self.repos.get_campaign(search_id) is None or self.repos.is_deleted(search_id):
            raise KeyError(search_id)
        campaign = self.get(search_id)
        if not is_terminal(campaign.state):
            self.cancellation.request(search_id)
            self.repos.update_open_tasks(search_id, TaskStatus.CANCELLED)
        disk = self.store.purge_campaign_private(search_id)
        removed_tables = self.repos.purge_campaign_private_rows(search_id)
        self.repos.redact_intent(search_id)
        self.repos.mark_deleted(search_id)
        self._usages.pop(search_id, None)
        removed = [
            "campaign-private object-store artifacts",
            "user reference uploads",
            "campaign events",
            "candidates and results",
            "user text and tags",
            *removed_tables,
        ]
        retained = [
            "receipts (including this DeletionReceipt)",
            "shared content-addressed objects still owned by other campaigns",
        ]
        receipt = DeletionReceipt(
            search_id=search_id,
            removed=removed,
            retained=retained,
            payload={
                "objects_removed": disk.get("objects", 0),
                "private_names_removed": disk.get("private_names", 0),
            },
        ).seal()
        self.store_receipt(receipt)
        return receipt

    def mark_step(self, search_id: str, step: str) -> None:
        runtime = self.repos.get_runtime(search_id)
        steps = list(runtime.get("completed_steps") or [])
        if step not in steps:
            steps.append(step)
        runtime["completed_steps"] = steps
        self.repos.update_runtime(search_id, runtime)

    def set_runtime(self, search_id: str, **fields: object) -> None:
        runtime = self.repos.get_runtime(search_id)
        runtime.update(fields)
        self.repos.update_runtime(search_id, runtime)

    def _emit(
        self,
        search_id: str,
        event_name: str,
        *,
        actor: str,
        state_version: int,
        payload: dict[str, object],
        input_digests: list[str] | None = None,
        output_digests: list[str] | None = None,
        error: str | None = None,
    ) -> CampaignEvent:
        predecessor = self.repos.last_event_id(search_id)
        event = CampaignEvent(
            search_id=search_id,
            state_version=state_version,
            actor=actor,
            input_digests=input_digests or [],
            output_digests=output_digests or [],
            predecessor=predecessor,
            error=error,
            event_name=event_name,
            payload=payload,
            timestamp=utc_now(),
        )
        return append_event(self.repos, event)

    def emit(
        self,
        search_id: str,
        event_name: str,
        *,
        payload: dict[str, object] | None = None,
        actor: str = "controller",
        input_digests: list[str] | None = None,
        output_digests: list[str] | None = None,
        error: str | None = None,
    ) -> CampaignEvent:
        campaign = self.get(search_id)
        return self._emit(
            search_id,
            event_name,
            actor=actor,
            state_version=campaign.state_version,
            payload=payload or {},
            input_digests=input_digests,
            output_digests=output_digests,
            error=error,
        )

    def now_iso(self) -> str:
        return format_utc(utc_now())
