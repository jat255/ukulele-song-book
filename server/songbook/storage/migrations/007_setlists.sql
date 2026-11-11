CREATE TABLE IF NOT EXISTS setlists (id TEXT PRIMARY KEY, title TEXT NOT NULL, revision TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS setlist_items (id TEXT PRIMARY KEY, setlist_id TEXT NOT NULL REFERENCES setlists(id) ON DELETE CASCADE, arrangement_id TEXT NOT NULL REFERENCES arrangements(id), position INTEGER NOT NULL, UNIQUE(setlist_id,position));
CREATE INDEX IF NOT EXISTS setlist_items_order ON setlist_items(setlist_id,position);
INSERT OR IGNORE INTO schema_migrations VALUES (7);
