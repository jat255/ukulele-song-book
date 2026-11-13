CREATE TABLE IF NOT EXISTS source_library_metadata (
 source_id TEXT PRIMARY KEY REFERENCES sources(id),
 revision INTEGER NOT NULL DEFAULT 0,
 deleted INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO schema_migrations VALUES (10);
