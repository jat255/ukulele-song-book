CREATE TABLE IF NOT EXISTS import_jobs (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id), selection_json TEXT NOT NULL,
 method TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0, worker_id TEXT, lease_until REAL, error_code TEXT,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS import_drafts (
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES import_jobs(id), ordinal INTEGER NOT NULL,
 source TEXT NOT NULL, revision TEXT NOT NULL, pages_json TEXT NOT NULL, diagnostics_json TEXT NOT NULL,
 accepted_id TEXT REFERENCES arrangements(id), accepting_revision TEXT, accepting_song_id TEXT, UNIQUE(job_id, ordinal)
);
CREATE TABLE IF NOT EXISTS worker_heartbeat (id INTEGER PRIMARY KEY CHECK(id=1), worker_id TEXT NOT NULL, last_seen REAL NOT NULL);
INSERT OR IGNORE INTO schema_migrations VALUES (3);
CREATE TABLE IF NOT EXISTS import_draft_provenance (
 draft_id TEXT PRIMARY KEY REFERENCES import_drafts(id), provider_json TEXT NOT NULL,
 provenance_json TEXT NOT NULL, uncertainty_json TEXT NOT NULL
);
