-- API wave: idempotent client keys and soft-delete. Receipts stay after delete.

ALTER TABLE campaigns ADD COLUMN client_search_id TEXT;
ALTER TABLE campaigns ADD COLUMN deleted_at TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_campaigns_client_search_id
    ON campaigns(client_search_id)
    WHERE client_search_id IS NOT NULL AND deleted_at IS NULL;
