-- Searcher wave-1 constitution schema (§27.1).
-- WAL and foreign keys are enabled by the connection layer.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    search_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    intent_json TEXT NOT NULL,
    budget_json TEXT NOT NULL,
    budget_used_json TEXT NOT NULL,
    coverage_json TEXT NOT NULL,
    novelty_history_json TEXT NOT NULL,
    runtime_json TEXT NOT NULL,
    terminal_status TEXT,
    terminal_reason TEXT,
    search_exhaustion_receipt TEXT,
    fixture_name TEXT,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    task_type TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL,
    input_digests_json TEXT NOT NULL,
    output_digests_json TEXT,
    adapter_version TEXT,
    backend_version TEXT,
    policy_version TEXT,
    parameters_json TEXT,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (search_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_tasks_search ON tasks(search_id);

CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hypotheses_search ON hypotheses(search_id);

CREATE TABLE IF NOT EXISTS queries (
    query_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    hypothesis_id TEXT,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_queries_search ON queries(search_id);

CREATE TABLE IF NOT EXISTS source_runs (
    source_run_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    source_id TEXT NOT NULL,
    cursor_json TEXT,
    last_outcome TEXT,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_source_runs_search ON source_runs(search_id);

CREATE TABLE IF NOT EXISTS fetch_attempts (
    attempt_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    content_digest TEXT,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fetch_attempts_search ON fetch_attempts(search_id);

CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    canonical_url TEXT NOT NULL,
    availability TEXT NOT NULL,
    cluster_id TEXT,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidates_search ON candidates(search_id);

CREATE TABLE IF NOT EXISTS candidate_images (
    listing_image_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
    content_digest TEXT,
    family_id TEXT,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidate_images_search ON candidate_images(search_id);

CREATE TABLE IF NOT EXISTS clusters (
    cluster_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    representative_id TEXT,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clusters_search ON clusters(search_id);

CREATE TABLE IF NOT EXISTS evidence_metadata (
    evidence_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    digest TEXT NOT NULL,
    family_id TEXT NOT NULL,
    polarity TEXT NOT NULL,
    accepted INTEGER NOT NULL,
    lineage_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_search ON evidence_metadata(search_id);
CREATE INDEX IF NOT EXISTS idx_evidence_accepted ON evidence_metadata(search_id, accepted);

CREATE TABLE IF NOT EXISTS scores (
    score_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    candidate_id TEXT,
    kind TEXT NOT NULL,
    mean REAL NOT NULL,
    lower_bound REAL NOT NULL,
    upper_bound REAL NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scores_search ON scores(search_id);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    candidate_id TEXT NOT NULL,
    internal TEXT NOT NULL,
    public TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_search ON decisions(search_id);

CREATE TABLE IF NOT EXISTS results (
    result_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    candidate_id TEXT NOT NULL,
    public_bucket TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_results_search ON results(search_id);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    result_id TEXT,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id TEXT PRIMARY KEY,
    search_id TEXT,
    receipt_type TEXT NOT NULL,
    digest TEXT NOT NULL,
    predecessor TEXT,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_receipts_search ON receipts(search_id);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    state_version INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL,
    input_digests_json TEXT NOT NULL,
    output_digests_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    predecessor TEXT,
    error TEXT,
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_search ON events(search_id);

CREATE TABLE IF NOT EXISTS budget_usage (
    search_id TEXT PRIMARY KEY REFERENCES campaigns(search_id),
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    state TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    label TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    receipt_ref TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_search ON checkpoints(search_id);

CREATE TABLE IF NOT EXISTS discovery_pages (
    page_id TEXT PRIMARY KEY,
    search_id TEXT NOT NULL REFERENCES campaigns(search_id),
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    cursor TEXT,
    outcome TEXT NOT NULL,
    content_digest TEXT,
    payload_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_discovery_pages_search ON discovery_pages(search_id);
