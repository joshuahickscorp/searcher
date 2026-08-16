-- Warm local index (§27.4 shared cache, §27.5 versioned keys).
-- Not campaign-private: delete of a campaign must not wipe these rows.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS index_listings (
    listing_key TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    parameters TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    source_adapter TEXT NOT NULL,
    source_listing_id TEXT,
    cluster_key TEXT,
    availability TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    title_norm TEXT,
    description_norm TEXT,
    ocr_terms TEXT NOT NULL,
    image_digests_json TEXT NOT NULL,
    perceptual_hashes_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_index_listings_url ON index_listings(canonical_url);
CREATE INDEX IF NOT EXISTS idx_index_listings_versions
    ON index_listings(adapter_version, model_version, schema_version, policy_version);

CREATE TABLE IF NOT EXISTS index_terms (
    term TEXT NOT NULL,
    listing_key TEXT NOT NULL REFERENCES index_listings(listing_key) ON DELETE CASCADE,
    field TEXT NOT NULL,
    tf INTEGER NOT NULL,
    PRIMARY KEY (term, listing_key, field)
);

CREATE INDEX IF NOT EXISTS idx_index_terms_term ON index_terms(term);

CREATE TABLE IF NOT EXISTS index_descriptors (
    listing_key TEXT NOT NULL REFERENCES index_listings(listing_key) ON DELETE CASCADE,
    image_digest TEXT NOT NULL,
    dim INTEGER NOT NULL,
    descriptor BLOB NOT NULL,
    kind TEXT NOT NULL,
    PRIMARY KEY (listing_key, image_digest)
);

CREATE TABLE IF NOT EXISTS index_evidence (
    evidence_key TEXT PRIMARY KEY,
    listing_key TEXT NOT NULL REFERENCES index_listings(listing_key) ON DELETE CASCADE,
    hypothesis_digest TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    parameters TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    item_match_mean REAL,
    item_match_lower REAL,
    item_match_upper REAL,
    authenticity_mean REAL,
    authenticity_lower REAL,
    authenticity_upper REAL,
    completeness REAL,
    destination_verified INTEGER NOT NULL DEFAULT 0,
    hard_vetoes_json TEXT NOT NULL,
    match_payload_json TEXT,
    authenticity_payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_index_evidence_listing ON index_evidence(listing_key);

CREATE TABLE IF NOT EXISTS index_queries (
    ior_key TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    query_norm TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    parameters TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    content_digest TEXT,
    last_run_at TEXT NOT NULL,
    pages INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_index_queries_source ON index_queries(source_id, query_norm);
