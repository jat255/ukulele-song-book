CREATE TABLE IF NOT EXISTS pdf_jobs (
 id TEXT PRIMARY KEY, arrangement_id TEXT NOT NULL REFERENCES arrangements(id), source_revision TEXT NOT NULL,
 payload_json TEXT NOT NULL, fingerprint TEXT NOT NULL, state TEXT NOT NULL, worker_id TEXT,
 lease_until REAL, attempts INTEGER NOT NULL DEFAULT 0, error_code TEXT, sha256 TEXT,
 page_count INTEGER, columns INTEGER, diagnostics_json TEXT NOT NULL DEFAULT '[]', renderer_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL
);
INSERT OR IGNORE INTO schema_migrations VALUES (6);
