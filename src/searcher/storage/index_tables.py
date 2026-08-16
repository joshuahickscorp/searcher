"""SQL for the warm local index. Callers go through WarmIndex, not this module."""

from __future__ import annotations

import json
from typing import Any

from searcher.core.time import format_utc, utc_now
from searcher.storage.connection import Database


def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _load_obj(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError("expected object JSON")
    return data


class IndexTables:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_listing(self, row: dict[str, Any]) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO index_listings (
                    listing_key, canonical_url, content_digest, adapter_version,
                    model_version, parameters, schema_version, policy_version,
                    source_adapter, source_listing_id, cluster_key, availability,
                    last_checked_at, first_seen_at, title_norm, description_norm,
                    ocr_terms, image_digests_json, perceptual_hashes_json,
                    payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(listing_key) DO UPDATE SET
                    availability = excluded.availability,
                    last_checked_at = excluded.last_checked_at,
                    cluster_key = excluded.cluster_key,
                    title_norm = excluded.title_norm,
                    description_norm = excluded.description_norm,
                    ocr_terms = excluded.ocr_terms,
                    image_digests_json = excluded.image_digests_json,
                    perceptual_hashes_json = excluded.perceptual_hashes_json,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    row["listing_key"],
                    row["canonical_url"],
                    row["content_digest"],
                    row["adapter_version"],
                    row["model_version"],
                    row["parameters"],
                    row["schema_version"],
                    row["policy_version"],
                    row["source_adapter"],
                    row.get("source_listing_id"),
                    row.get("cluster_key"),
                    row["availability"],
                    row["last_checked_at"],
                    row["first_seen_at"],
                    row.get("title_norm"),
                    row.get("description_norm"),
                    row.get("ocr_terms") or "[]",
                    _dump(row.get("image_digests") or []),
                    _dump(row.get("perceptual_hashes") or []),
                    _dump(row["payload"]),
                    now,
                    now,
                ),
            )

    def get_listing(self, listing_key: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM index_listings WHERE listing_key = ?",
            (listing_key,),
        ).fetchone()
        return self._listing_from_row(row) if row is not None else None

    def get_listing_by_url(
        self,
        canonical_url: str,
        *,
        adapter_version: str,
        model_version: str,
        parameters: str,
        schema_version: str,
        policy_version: str,
    ) -> dict[str, Any] | None:
        row = self.db.execute(
            """
            SELECT * FROM index_listings
            WHERE canonical_url = ?
              AND adapter_version = ?
              AND model_version = ?
              AND parameters = ?
              AND schema_version = ?
              AND policy_version = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (
                canonical_url,
                adapter_version,
                model_version,
                parameters,
                schema_version,
                policy_version,
            ),
        ).fetchone()
        return self._listing_from_row(row) if row is not None else None

    def replace_terms(self, listing_key: str, entries: list[tuple[str, str, int]]) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM index_terms WHERE listing_key = ?", (listing_key,))
            conn.executemany(
                """
                INSERT INTO index_terms (term, listing_key, field, tf)
                VALUES (?, ?, ?, ?)
                """,
                [(term, listing_key, field, tf) for term, field, tf in entries],
            )

    def replace_descriptors(
        self, listing_key: str, entries: list[tuple[str, int, bytes, str]]
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM index_descriptors WHERE listing_key = ?", (listing_key,))
            conn.executemany(
                """
                INSERT INTO index_descriptors (
                    listing_key, image_digest, dim, descriptor, kind
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [(listing_key, digest, dim, blob, kind) for digest, dim, blob, kind in entries],
            )

    def list_descriptors(self, listing_key: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT * FROM index_descriptors WHERE listing_key = ?",
            (listing_key,),
        ).fetchall()
        return [dict(row) for row in rows]

    def search_listings(
        self,
        terms: list[str],
        *,
        adapter_version: str,
        model_version: str,
        parameters: str,
        schema_version: str,
        policy_version: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not terms:
            return []
        placeholders = ",".join("?" * len(terms))
        sql = f"""
            SELECT l.*, SUM(t.tf) AS term_score
            FROM index_terms t
            JOIN index_listings l ON l.listing_key = t.listing_key
            WHERE t.term IN ({placeholders})
              AND l.adapter_version = ?
              AND l.model_version = ?
              AND l.parameters = ?
              AND l.schema_version = ?
              AND l.policy_version = ?
            GROUP BY l.listing_key
            ORDER BY term_score DESC
            LIMIT ?
        """
        rows = self.db.execute(
            sql,
            (
                *terms,
                adapter_version,
                model_version,
                parameters,
                schema_version,
                policy_version,
                limit,
            ),
        ).fetchall()
        return [self._listing_from_row(row) for row in rows]

    def upsert_evidence(self, row: dict[str, Any]) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO index_evidence (
                    evidence_key, listing_key, hypothesis_digest, adapter_version,
                    model_version, parameters, schema_version, policy_version,
                    item_match_mean, item_match_lower, item_match_upper,
                    authenticity_mean, authenticity_lower, authenticity_upper,
                    completeness, destination_verified, hard_vetoes_json,
                    match_payload_json, authenticity_payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evidence_key) DO UPDATE SET
                    item_match_mean = excluded.item_match_mean,
                    item_match_lower = excluded.item_match_lower,
                    item_match_upper = excluded.item_match_upper,
                    authenticity_mean = excluded.authenticity_mean,
                    authenticity_lower = excluded.authenticity_lower,
                    authenticity_upper = excluded.authenticity_upper,
                    completeness = excluded.completeness,
                    destination_verified = excluded.destination_verified,
                    hard_vetoes_json = excluded.hard_vetoes_json,
                    match_payload_json = excluded.match_payload_json,
                    authenticity_payload_json = excluded.authenticity_payload_json
                """,
                (
                    row["evidence_key"],
                    row["listing_key"],
                    row["hypothesis_digest"],
                    row["adapter_version"],
                    row["model_version"],
                    row["parameters"],
                    row["schema_version"],
                    row["policy_version"],
                    row.get("item_match_mean"),
                    row.get("item_match_lower"),
                    row.get("item_match_upper"),
                    row.get("authenticity_mean"),
                    row.get("authenticity_lower"),
                    row.get("authenticity_upper"),
                    row.get("completeness"),
                    1 if row.get("destination_verified") else 0,
                    _dump(row.get("hard_vetoes") or []),
                    _dump(row["match_payload"]) if row.get("match_payload") else None,
                    _dump(row["authenticity_payload"]) if row.get("authenticity_payload") else None,
                    now,
                ),
            )

    def get_evidence(self, evidence_key: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM index_evidence WHERE evidence_key = ?",
            (evidence_key,),
        ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["hard_vetoes"] = json.loads(row["hard_vetoes_json"] or "[]")
        match_raw = row["match_payload_json"]
        auth_raw = row["authenticity_payload_json"]
        item["match_payload"] = _load_obj(match_raw) if match_raw else None
        item["authenticity_payload"] = _load_obj(auth_raw) if auth_raw else None
        item["destination_verified"] = bool(row["destination_verified"])
        return item

    def upsert_query(self, row: dict[str, Any]) -> None:
        now = format_utc(utc_now())
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO index_queries (
                    ior_key, source_id, query_norm, adapter_version, model_version,
                    parameters, schema_version, policy_version, content_digest,
                    last_run_at, pages
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ior_key) DO UPDATE SET
                    content_digest = excluded.content_digest,
                    last_run_at = excluded.last_run_at,
                    pages = excluded.pages
                """,
                (
                    row["ior_key"],
                    row["source_id"],
                    row["query_norm"],
                    row["adapter_version"],
                    row["model_version"],
                    row["parameters"],
                    row["schema_version"],
                    row["policy_version"],
                    row.get("content_digest"),
                    row.get("last_run_at") or now,
                    int(row.get("pages") or 0),
                ),
            )

    def get_query(self, ior_key: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM index_queries WHERE ior_key = ?",
            (ior_key,),
        ).fetchone()
        return dict(row) if row is not None else None

    def count_listings(self) -> int:
        row = self.db.execute("SELECT COUNT(*) AS n FROM index_listings").fetchone()
        return int(row["n"]) if row is not None else 0

    def _listing_from_row(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["payload"] = _load_obj(row["payload_json"])
        item["image_digests"] = json.loads(row["image_digests_json"] or "[]")
        item["perceptual_hashes"] = json.loads(row["perceptual_hashes_json"] or "[]")
        item["ocr_terms"] = json.loads(row["ocr_terms"] or "[]")
        return item
