CREATE TABLE IF NOT EXISTS arrangement_preferences (
 arrangement_id TEXT PRIMARY KEY REFERENCES arrangements(id), document_json TEXT NOT NULL, etag TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_migrations VALUES (5);
CREATE TABLE IF NOT EXISTS app_preferences (id INTEGER PRIMARY KEY CHECK(id=1), document_json TEXT NOT NULL, etag TEXT NOT NULL);
