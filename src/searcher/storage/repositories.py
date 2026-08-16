"""Typed read/write access. Callers never write SQL."""

from __future__ import annotations

import json
from typing import Any

from searcher import SCHEMA_VERSION
from searcher.contracts.enums import CampaignState, TaskStatus
from searcher.contracts.models import (
    BucketDecision,
    DiscoveryPage,
    FetchAttempt,
    ItemHypothesis,
    ListingCandidate,
    ListingImage,
    QueryVariant,
    SearchCampaign,
    SearchIntent,
)
from searcher.core.errors import StaleStateVersion
from searcher.core.time import format_utc, utc_now
from searcher.evidence.records import EvidenceRecord
from searcher.storage.connection import Database


def _dump(value: object) -> str:
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"), sort_keys=True)
    return json.dumps(value, sort_keys=True, default=str)


def _load(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError("expected object JSON")
    return data


class Repositories:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert_campaign(
        self,
        campaign: SearchCampaign,
        *,
        intent: SearchIntent,
        budget: dict[str, Any],
        runtime: dict[str, Any] | None = None,
    ) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO campaigns (
                    search_id, state, state_version, intent_json, budget_json,
                    budget_used_json, coverage_json, novelty_history_json, runtime_json,
                    terminal_status, terminal_reason, search_exhaustion_receipt,
                    fixture_name, schema_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign.search_id,
                    campaign.state.value,
                    campaign.state_version,
                    _dump(intent),
                    json.dumps(budget, sort_keys=True, default=str),
                    json.dumps(campaign.budget_used, sort_keys=True, default=str),
                    json.dumps(campaign.coverage, sort_keys=True, default=str),
                    json.dumps(campaign.novelty_history),
                    json.dumps(runtime or {}, sort_keys=True, default=str),
                    campaign.terminal_status.value if campaign.terminal_status else None,
                    campaign.terminal_reason,
                    campaign.search_exhaustion_receipt,
                    campaign.fixture_name,
                    campaign.schema_version,
                    now,
                    now,
                ),
            )

    def get_campaign(self, search_id: str) -> SearchCampaign | None:
        row = self.db.execute(
            "SELECT * FROM campaigns WHERE search_id = ?", (search_id,)
        ).fetchone()
        if row is None:
            return None
        return self._campaign_from_row(row)

    def get_intent(self, search_id: str) -> SearchIntent:
        row = self.db.execute(
            "SELECT intent_json FROM campaigns WHERE search_id = ?", (search_id,)
        ).fetchone()
        if row is None:
            raise KeyError(search_id)
        return SearchIntent.model_validate(_load(row["intent_json"]))

    def get_runtime(self, search_id: str) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT runtime_json FROM campaigns WHERE search_id = ?", (search_id,)
        ).fetchone()
        if row is None:
            raise KeyError(search_id)
        return _load(row["runtime_json"])

    def get_budget_payload(self, search_id: str) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT budget_json FROM campaigns WHERE search_id = ?", (search_id,)
        ).fetchone()
        if row is None:
            raise KeyError(search_id)
        return _load(row["budget_json"])

    def update_runtime(self, search_id: str, runtime: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE campaigns SET runtime_json = ?, updated_at = ? WHERE search_id = ?",
                (
                    json.dumps(runtime, sort_keys=True, default=str),
                    format_utc(utc_now()),
                    search_id,
                ),
            )

    def update_campaign_blob(
        self,
        campaign: SearchCampaign,
        *,
        expected_version: int,
        runtime: dict[str, Any] | None = None,
    ) -> int:
        """Optimistic-concurrency state write. Returns the new state_version."""
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            cur = conn.execute(
                """
                UPDATE campaigns SET
                    state = ?,
                    state_version = state_version + 1,
                    budget_used_json = ?,
                    coverage_json = ?,
                    novelty_history_json = ?,
                    runtime_json = COALESCE(?, runtime_json),
                    terminal_status = ?,
                    terminal_reason = ?,
                    search_exhaustion_receipt = ?,
                    updated_at = ?
                WHERE search_id = ? AND state_version = ?
                """,
                (
                    campaign.state.value,
                    json.dumps(campaign.budget_used, sort_keys=True, default=str),
                    json.dumps(campaign.coverage, sort_keys=True, default=str),
                    json.dumps(campaign.novelty_history),
                    json.dumps(runtime, sort_keys=True, default=str)
                    if runtime is not None
                    else None,
                    campaign.terminal_status.value if campaign.terminal_status else None,
                    campaign.terminal_reason,
                    campaign.search_exhaustion_receipt,
                    now,
                    campaign.search_id,
                    expected_version,
                ),
            )
            if cur.rowcount != 1:
                actual_row = conn.execute(
                    "SELECT state_version FROM campaigns WHERE search_id = ?",
                    (campaign.search_id,),
                ).fetchone()
                actual = int(actual_row["state_version"]) if actual_row else None
                raise StaleStateVersion(
                    "stale campaign write rejected",
                    search_id=campaign.search_id,
                    expected=expected_version,
                    actual=actual,
                )
            new_version = expected_version + 1
            return new_version

    def _campaign_from_row(self, row: Any) -> SearchCampaign:
        intent = SearchIntent.model_validate(_load(row["intent_json"]))
        hypotheses = [
            str(r["hypothesis_id"])
            for r in self.db.execute(
                "SELECT hypothesis_id FROM hypotheses WHERE search_id = ?",
                (row["search_id"],),
            ).fetchall()
        ]
        queries = [
            str(r["query_id"])
            for r in self.db.execute(
                "SELECT query_id FROM queries WHERE search_id = ?",
                (row["search_id"],),
            ).fetchall()
        ]
        source_runs = [
            str(r["source_run_id"])
            for r in self.db.execute(
                "SELECT source_run_id FROM source_runs WHERE search_id = ?",
                (row["search_id"],),
            ).fetchall()
        ]
        candidates = [
            str(r["candidate_id"])
            for r in self.db.execute(
                "SELECT candidate_id FROM candidates WHERE search_id = ?",
                (row["search_id"],),
            ).fetchall()
        ]
        results = [
            str(r["result_id"])
            for r in self.db.execute(
                "SELECT result_id FROM results WHERE search_id = ?",
                (row["search_id"],),
            ).fetchall()
        ]
        checkpoints = [
            str(r["checkpoint_id"])
            for r in self.db.execute(
                "SELECT checkpoint_id FROM checkpoints WHERE search_id = ? ORDER BY created_at",
                (row["search_id"],),
            ).fetchall()
        ]
        terminal = row["terminal_status"]
        return SearchCampaign(
            search_id=row["search_id"],
            state=CampaignState(row["state"]),
            state_version=int(row["state_version"]),
            intent_ref=intent.search_id,
            hypothesis_ids=hypotheses,
            query_ids=queries,
            source_run_ids=source_runs,
            candidate_ids=candidates,
            result_ids=results,
            budget_used=_load(row["budget_used_json"]) if row["budget_used_json"] else {},
            coverage=_load(row["coverage_json"]) if row["coverage_json"] else {},
            novelty_history=json.loads(row["novelty_history_json"] or "[]"),
            checkpoints=checkpoints,
            terminal_status=terminal,
            terminal_reason=row["terminal_reason"],
            search_exhaustion_receipt=row["search_exhaustion_receipt"],
            fixture_name=row["fixture_name"],
            schema_version=row["schema_version"],
        )

    def upsert_hypothesis(self, hyp: ItemHypothesis) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO hypotheses (
                    hypothesis_id, search_id, status, payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(hypothesis_id) DO UPDATE SET
                    status = excluded.status,
                    payload_json = excluded.payload_json
                """,
                (
                    hyp.hypothesis_id,
                    hyp.search_id,
                    hyp.status.value,
                    _dump(hyp),
                    hyp.schema_version,
                    now,
                ),
            )

    def list_hypotheses(self, search_id: str) -> list[ItemHypothesis]:
        rows = self.db.execute(
            "SELECT payload_json FROM hypotheses WHERE search_id = ?", (search_id,)
        ).fetchall()
        return [ItemHypothesis.model_validate(_load(r["payload_json"])) for r in rows]

    def upsert_query(self, search_id: str, query: QueryVariant) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO queries (
                    query_id, search_id, hypothesis_id, status,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(query_id) DO UPDATE SET
                    status = excluded.status,
                    payload_json = excluded.payload_json
                """,
                (
                    query.query_id,
                    search_id,
                    query.hypothesis_id,
                    query.status.value,
                    _dump(query),
                    query.schema_version,
                    now,
                ),
            )

    def list_queries(self, search_id: str) -> list[QueryVariant]:
        rows = self.db.execute(
            "SELECT payload_json FROM queries WHERE search_id = ?", (search_id,)
        ).fetchall()
        return [QueryVariant.model_validate(_load(r["payload_json"])) for r in rows]

    def upsert_source_run(
        self,
        search_id: str,
        source_run_id: str,
        source_id: str,
        *,
        cursor: str | None,
        last_outcome: str | None,
        payload: dict[str, Any],
    ) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO source_runs (
                    source_run_id, search_id, source_id, cursor_json, last_outcome,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_run_id) DO UPDATE SET
                    cursor_json = excluded.cursor_json,
                    last_outcome = excluded.last_outcome,
                    payload_json = excluded.payload_json
                """,
                (
                    source_run_id,
                    search_id,
                    source_id,
                    cursor,
                    last_outcome,
                    json.dumps(payload, sort_keys=True, default=str),
                    SCHEMA_VERSION,
                    now,
                ),
            )

    def list_source_runs(self, search_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM source_runs WHERE search_id = ?", (search_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def insert_fetch_attempt(self, search_id: str, attempt: FetchAttempt) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO fetch_attempts (
                    attempt_id, search_id, source_id, url, status, content_digest,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.attempt_id,
                    search_id,
                    attempt.source_id,
                    attempt.url,
                    attempt.status.value,
                    attempt.content_digest,
                    _dump(attempt),
                    attempt.schema_version,
                    now,
                ),
            )

    def list_fetch_attempts(self, search_id: str) -> list[FetchAttempt]:
        rows = self.db.execute(
            "SELECT payload_json FROM fetch_attempts WHERE search_id = ?", (search_id,)
        ).fetchall()
        return [FetchAttempt.model_validate(_load(r["payload_json"])) for r in rows]

    def upsert_candidate(self, search_id: str, candidate: ListingCandidate) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO candidates (
                    candidate_id, search_id, canonical_url, availability, cluster_id,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    availability = excluded.availability,
                    cluster_id = excluded.cluster_id,
                    payload_json = excluded.payload_json
                """,
                (
                    candidate.candidate_id,
                    search_id,
                    candidate.canonical_url,
                    candidate.availability.value,
                    candidate.cluster_id,
                    _dump(candidate),
                    candidate.schema_version,
                    now,
                ),
            )
            for image in candidate.images:
                self._upsert_image(conn, search_id, image, now)

    def _upsert_image(self, conn: Any, search_id: str, image: ListingImage, now: str) -> None:
        conn.execute(
            """
            INSERT INTO candidate_images (
                listing_image_id, search_id, candidate_id, content_digest, family_id,
                payload_json, schema_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(listing_image_id) DO UPDATE SET
                content_digest = excluded.content_digest,
                family_id = excluded.family_id,
                payload_json = excluded.payload_json
            """,
            (
                image.listing_image_id,
                search_id,
                image.candidate_id,
                image.content_digest,
                image.duplicate_family_id,
                _dump(image),
                image.schema_version,
                now,
            ),
        )

    def list_candidates(self, search_id: str) -> list[ListingCandidate]:
        rows = self.db.execute(
            "SELECT payload_json FROM candidates WHERE search_id = ?", (search_id,)
        ).fetchall()
        return [ListingCandidate.model_validate(_load(r["payload_json"])) for r in rows]

    def insert_cluster(
        self,
        search_id: str,
        cluster_id: str,
        representative_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO clusters (
                    cluster_id, search_id, representative_id,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cluster_id) DO UPDATE SET
                    representative_id = excluded.representative_id,
                    payload_json = excluded.payload_json
                """,
                (
                    cluster_id,
                    search_id,
                    representative_id,
                    json.dumps(payload, sort_keys=True, default=str),
                    SCHEMA_VERSION,
                    now,
                ),
            )

    def insert_evidence(self, record: EvidenceRecord) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO evidence_metadata (
                    evidence_id, search_id, digest, family_id, polarity, accepted,
                    lineage_json, payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.evidence_id,
                    record.search_id,
                    record.content_digest,
                    record.family_id,
                    record.polarity.value,
                    1 if record.accepted else 0,
                    _dump(record.lineage),
                    _dump(record),
                    record.schema_version,
                    format_utc(record.created_at),
                ),
            )

    def list_evidence(self, search_id: str, *, accepted_only: bool = False) -> list[EvidenceRecord]:
        sql = "SELECT payload_json FROM evidence_metadata WHERE search_id = ?"
        params: tuple[object, ...] = (search_id,)
        if accepted_only:
            sql += " AND accepted = 1"
        rows = self.db.execute(sql, params).fetchall()
        return [EvidenceRecord.model_validate(_load(r["payload_json"])) for r in rows]

    def insert_score(
        self,
        search_id: str,
        score_id: str,
        kind: str,
        mean: float,
        lower_bound: float,
        upper_bound: float,
        payload: dict[str, Any],
        candidate_id: str | None = None,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO scores (
                    score_id, search_id, candidate_id, kind, mean, lower_bound, upper_bound,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    score_id,
                    search_id,
                    candidate_id,
                    kind,
                    mean,
                    lower_bound,
                    upper_bound,
                    json.dumps(payload, sort_keys=True, default=str),
                    SCHEMA_VERSION,
                    format_utc(utc_now()),
                ),
            )

    def list_scores(self, search_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM scores WHERE search_id = ?", (search_id,)).fetchall()
        return [dict(r) for r in rows]

    def insert_decision(self, search_id: str, decision_id: str, decision: BucketDecision) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO decisions (
                    decision_id, search_id, candidate_id, internal, public,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    search_id,
                    decision.candidate_id,
                    decision.decision.internal.value,
                    decision.decision.public.value,
                    _dump(decision),
                    decision.schema_version,
                    format_utc(utc_now()),
                ),
            )

    def list_decisions(self, search_id: str) -> list[BucketDecision]:
        rows = self.db.execute(
            "SELECT payload_json FROM decisions WHERE search_id = ?", (search_id,)
        ).fetchall()
        return [BucketDecision.model_validate(_load(r["payload_json"])) for r in rows]

    def insert_result(
        self,
        search_id: str,
        result_id: str,
        candidate_id: str,
        public_bucket: str,
        payload: dict[str, Any],
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO results (
                    result_id, search_id, candidate_id, public_bucket,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    search_id,
                    candidate_id,
                    public_bucket,
                    json.dumps(payload, sort_keys=True, default=str),
                    SCHEMA_VERSION,
                    format_utc(utc_now()),
                ),
            )

    def list_results(self, search_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT * FROM results WHERE search_id = ?", (search_id,)).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = _load(row["payload_json"])
            out.append(item)
        return out

    def insert_feedback(
        self,
        search_id: str,
        feedback_id: str,
        kind: str,
        payload: dict[str, Any],
        result_id: str | None = None,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO feedback (
                    feedback_id, search_id, result_id, kind,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    search_id,
                    result_id,
                    kind,
                    json.dumps(payload, sort_keys=True, default=str),
                    SCHEMA_VERSION,
                    format_utc(utc_now()),
                ),
            )

    def get_task_by_key(self, search_id: str, key: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM tasks WHERE search_id = ? AND idempotency_key = ?",
            (search_id, key),
        ).fetchone()
        return dict(row) if row is not None else None

    def insert_task(
        self,
        search_id: str,
        task_id: str,
        task_type: str,
        idempotency_key: str,
        *,
        status: TaskStatus,
        input_digests: list[str],
        output_digests: list[str] | None,
        adapter_version: str,
        backend_version: str,
        policy_version: str,
        parameters: dict[str, Any],
        payload: dict[str, Any],
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    task_id, search_id, task_type, idempotency_key, status,
                    input_digests_json, output_digests_json, adapter_version,
                    backend_version, policy_version, parameters_json, payload_json,
                    schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    search_id,
                    task_type,
                    idempotency_key,
                    status.value,
                    json.dumps(input_digests),
                    json.dumps(output_digests or []),
                    adapter_version,
                    backend_version,
                    policy_version,
                    json.dumps(parameters, sort_keys=True, default=str),
                    json.dumps(payload, sort_keys=True, default=str),
                    SCHEMA_VERSION,
                    format_utc(utc_now()),
                ),
            )

    def list_tasks(self, search_id: str) -> list[dict[str, Any]]:
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM tasks WHERE search_id = ?", (search_id,)
            ).fetchall()
        ]

    def insert_event(self, payload: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    event_id, search_id, state_version, event_name, timestamp, actor,
                    input_digests_json, output_digests_json, schema_version,
                    predecessor, error, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["event_id"],
                    payload["search_id"],
                    payload["state_version"],
                    payload["event_name"],
                    payload["timestamp"],
                    payload["actor"],
                    json.dumps(payload.get("input_digests") or []),
                    json.dumps(payload.get("output_digests") or []),
                    payload["schema_version"],
                    payload.get("predecessor"),
                    payload.get("error"),
                    json.dumps(payload, sort_keys=True, default=str),
                ),
            )

    def list_events(self, search_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT payload_json FROM events WHERE search_id = ? ORDER BY rowid",
            (search_id,),
        ).fetchall()
        return [_load(r["payload_json"]) for r in rows]

    def last_event_id(self, search_id: str) -> str | None:
        row = self.db.execute(
            "SELECT event_id FROM events WHERE search_id = ? ORDER BY rowid DESC LIMIT 1",
            (search_id,),
        ).fetchone()
        return str(row["event_id"]) if row else None

    def insert_receipt(self, payload: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO receipts (
                    receipt_id, search_id, receipt_type, digest, predecessor,
                    payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["receipt_id"],
                    payload.get("search_id"),
                    payload["receipt_type"],
                    payload["digest"],
                    payload.get("predecessor"),
                    json.dumps(payload, sort_keys=True, default=str),
                    payload.get("schema_version", SCHEMA_VERSION),
                    payload.get("created_at", format_utc(utc_now())),
                ),
            )

    def get_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT payload_json FROM receipts WHERE receipt_id = ?", (receipt_id,)
        ).fetchone()
        return _load(row["payload_json"]) if row else None

    def list_receipts(self, search_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT payload_json FROM receipts WHERE search_id = ? ORDER BY rowid",
            (search_id,),
        ).fetchall()
        return [_load(r["payload_json"]) for r in rows]

    def insert_checkpoint(self, payload: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (
                    checkpoint_id, search_id, state, state_version, label,
                    payload_json, receipt_ref, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["checkpoint_id"],
                    payload["search_id"],
                    payload["state"],
                    payload["state_version"],
                    payload["label"],
                    json.dumps(payload, sort_keys=True, default=str),
                    payload.get("receipt_ref"),
                    payload["created_at"],
                ),
            )

    def list_checkpoints(self, search_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT payload_json FROM checkpoints WHERE search_id = ? ORDER BY rowid",
            (search_id,),
        ).fetchall()
        return [_load(r["payload_json"]) for r in rows]

    def last_checkpoint(self, search_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT payload_json FROM checkpoints WHERE search_id = ? ORDER BY rowid DESC LIMIT 1",
            (search_id,),
        ).fetchone()
        return _load(row["payload_json"]) if row else None

    def insert_discovery_page(self, page: DiscoveryPage) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO discovery_pages (
                    page_id, search_id, source_id, url, cursor, outcome,
                    content_digest, payload_json, schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    page.page_id,
                    page.search_id,
                    page.source_id,
                    page.url,
                    page.cursor,
                    page.outcome.value,
                    page.content_digest,
                    _dump(page),
                    page.schema_version,
                    format_utc(utc_now()),
                ),
            )

    def list_discovery_pages(self, search_id: str) -> list[DiscoveryPage]:
        rows = self.db.execute(
            "SELECT payload_json FROM discovery_pages WHERE search_id = ?", (search_id,)
        ).fetchall()
        return [DiscoveryPage.model_validate(_load(r["payload_json"])) for r in rows]

    def upsert_budget_usage(self, search_id: str, payload: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO budget_usage (search_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(search_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    search_id,
                    json.dumps(payload, sort_keys=True, default=str),
                    format_utc(utc_now()),
                ),
            )

    def get_budget_usage(self, search_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT payload_json FROM budget_usage WHERE search_id = ?", (search_id,)
        ).fetchone()
        return _load(row["payload_json"]) if row else None

    def upsert_frontier_item(self, item: dict[str, Any]) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO frontier (
                    run_id, work_key, search_id, source_id, url, kind, depth, priority,
                    state, attempts, cursor, last_error_class, last_outcome,
                    payload_json, schema_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, work_key) DO UPDATE SET
                    priority = excluded.priority,
                    state = excluded.state,
                    attempts = excluded.attempts,
                    cursor = excluded.cursor,
                    last_error_class = excluded.last_error_class,
                    last_outcome = excluded.last_outcome,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    item["run_id"],
                    item["work_key"],
                    item["search_id"],
                    item["source_id"],
                    item["url"],
                    item["kind"],
                    int(item["depth"]),
                    float(item["priority"]),
                    item["state"],
                    int(item.get("attempts", 0)),
                    item.get("cursor"),
                    item.get("last_error_class"),
                    item.get("last_outcome"),
                    json.dumps(item.get("payload") or {}, sort_keys=True, default=str),
                    item.get("schema_version", SCHEMA_VERSION),
                    item.get("created_at", now),
                    now,
                ),
            )

    def get_frontier_item(self, run_id: str, work_key: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM frontier WHERE run_id = ? AND work_key = ?",
            (run_id, work_key),
        ).fetchone()
        return dict(row) if row is not None else None

    def list_frontier(self, run_id: str, *, state: str | None = None) -> list[dict[str, Any]]:
        if state is None:
            rows = self.db.execute(
                "SELECT * FROM frontier WHERE run_id = ? ORDER BY priority DESC, created_at",
                (run_id,),
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM frontier WHERE run_id = ? AND state = ? "
                "ORDER BY priority DESC, created_at",
                (run_id, state),
            ).fetchall()
        return [dict(r) for r in rows]

    def pop_frontier_batch(self, run_id: str, limit: int) -> list[dict[str, Any]]:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM frontier WHERE run_id = ? AND state = 'pending' "
                "ORDER BY priority DESC, created_at LIMIT ?",
                (run_id, limit),
            ).fetchall()
            claimed: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                conn.execute(
                    "UPDATE frontier SET state = 'inflight', attempts = attempts + 1, "
                    "updated_at = ? WHERE run_id = ? AND work_key = ? AND state = 'pending'",
                    (now, run_id, item["work_key"]),
                )
                item["state"] = "inflight"
                item["attempts"] = int(item["attempts"]) + 1
                claimed.append(item)
            return claimed

    def recover_stale_inflight(self, run_id: str, older_than: str) -> int:
        with self.db.transaction() as conn:
            cur = conn.execute(
                "UPDATE frontier SET state = 'pending', updated_at = ? "
                "WHERE run_id = ? AND state = 'inflight' AND updated_at < ?",
                (format_utc(utc_now()), run_id, older_than),
            )
            return int(cur.rowcount)

    def upsert_response_cache(self, item: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO response_cache (
                    url_canonical, etag, last_modified, content_digest, body_ref,
                    fetched_at, policy, headers_json, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url_canonical) DO UPDATE SET
                    etag = excluded.etag,
                    last_modified = excluded.last_modified,
                    content_digest = excluded.content_digest,
                    body_ref = excluded.body_ref,
                    fetched_at = excluded.fetched_at,
                    policy = excluded.policy,
                    headers_json = excluded.headers_json
                """,
                (
                    item["url_canonical"],
                    item.get("etag"),
                    item.get("last_modified"),
                    item["content_digest"],
                    item["body_ref"],
                    item["fetched_at"],
                    item.get("policy"),
                    json.dumps(item.get("headers") or {}, sort_keys=True),
                    item.get("schema_version", SCHEMA_VERSION),
                ),
            )

    def get_response_cache(self, url_canonical: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM response_cache WHERE url_canonical = ?",
            (url_canonical,),
        ).fetchone()
        return dict(row) if row is not None else None

    def upsert_source_health_row(self, item: dict[str, Any]) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO source_health (
                    source_id, consecutive_failures, breaker_open_until, last_success_at,
                    last_block_class, last_outcome, state, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    consecutive_failures = excluded.consecutive_failures,
                    breaker_open_until = excluded.breaker_open_until,
                    last_success_at = excluded.last_success_at,
                    last_block_class = excluded.last_block_class,
                    last_outcome = excluded.last_outcome,
                    state = excluded.state,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    item["source_id"],
                    int(item.get("consecutive_failures", 0)),
                    item.get("breaker_open_until"),
                    item.get("last_success_at"),
                    item.get("last_block_class"),
                    item.get("last_outcome"),
                    item.get("state", "HEALTHY"),
                    json.dumps(item.get("payload") or {}, sort_keys=True, default=str),
                    format_utc(utc_now()),
                ),
            )

    def get_source_health_row(self, source_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM source_health WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def upsert_robots_cache(
        self, origin: str, body: str, status: str, crawl_delay: float | None
    ) -> None:  # noqa: E501
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO robots_cache (origin, body, fetched_at, crawl_delay, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(origin) DO UPDATE SET
                    body = excluded.body,
                    fetched_at = excluded.fetched_at,
                    crawl_delay = excluded.crawl_delay,
                    status = excluded.status
                """,
                (origin, body, format_utc(utc_now()), crawl_delay, status),
            )

    def get_robots_cache(self, origin: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM robots_cache WHERE origin = ?",
            (origin,),
        ).fetchone()
        return dict(row) if row is not None else None
