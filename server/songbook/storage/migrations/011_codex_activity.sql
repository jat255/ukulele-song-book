CREATE TABLE IF NOT EXISTS codex_job_activity (job_id TEXT PRIMARY KEY REFERENCES import_jobs(id) ON DELETE CASCADE, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bulk_import_identity (source_sha256 TEXT NOT NULL, draft_sha256 TEXT NOT NULL, job_id TEXT NOT NULL, PRIMARY KEY(source_sha256,draft_sha256));
INSERT OR IGNORE INTO schema_migrations VALUES (11);
