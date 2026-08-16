-- Wave 2 discovery/acquisition tables. Ideas from donor db.SCHEMA
-- (jobs PK, http_cache, company_state, fetch_log) reimplemented without CRM columns.
-- Provenance: frozen snapshot manifest
-- 3a2c41c8306e422ad42ede9da145891a72ec8e691bf32e8a407ead899facced2

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS frontier (
    run_id TEXT NOT NULL,
    work_key TEXT NOT NULL,
    search_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    kind TEXT NOT NULL,
    depth INTEGER NOT NULL,
    priority REAL NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    cursor TEXT,
    last_error_class TEXT,
    last_outcome TEXT,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, work_key)
);

CREATE INDEX IF NOT EXISTS idx_frontier_pop
    ON frontier(run_id, state, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_frontier_search ON frontier(search_id);

CREATE TABLE IF NOT EXISTS response_cache (
    url_canonical TEXT PRIMARY KEY,
    etag TEXT,
    last_modified TEXT,
    content_digest TEXT NOT NULL,
    body_ref TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    policy TEXT,
    headers_json TEXT,
    schema_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_health (
    source_id TEXT PRIMARY KEY,
    consecutive_failures INTEGER NOT NULL,
    breaker_open_until TEXT,
    last_success_at TEXT,
    last_block_class TEXT,
    last_outcome TEXT,
    state TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS robots_cache (
    origin TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    crawl_delay REAL,
    status TEXT NOT NULL
);
