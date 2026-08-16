-- Matching and authenticity artifacts. Additive; wave-1 tables stay untouched.

CREATE TABLE IF NOT EXISTS comparison_artifacts (
    artifact_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    candidate_id TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_comparison_artifacts_search ON comparison_artifacts(search_id);

CREATE TABLE IF NOT EXISTS cost_ledgers (
    ledger_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cost_ledgers_search ON cost_ledgers(search_id);
