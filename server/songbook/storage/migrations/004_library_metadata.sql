CREATE TABLE IF NOT EXISTS library_metadata (
 arrangement_id TEXT PRIMARY KEY REFERENCES arrangements(id), revision INTEGER NOT NULL DEFAULT 1,
 favorite INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', last_played REAL, deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS library_tags (
 arrangement_id TEXT NOT NULL REFERENCES arrangements(id), tag TEXT NOT NULL,
 PRIMARY KEY(arrangement_id, tag)
);
CREATE INDEX IF NOT EXISTS library_tags_tag ON library_tags(tag);
INSERT OR IGNORE INTO schema_migrations VALUES (4);
