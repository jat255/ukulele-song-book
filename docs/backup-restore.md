# Local backup and restore

A backup contains a consistent private snapshot of managed files and SQLite,
including the password hash. The snapshot holds the managed-file lock and a
SQLite write reservation while files and database state are copied. Existing
writes finish first; new writes wait. Interrupted writes are recovered before
snapshotting. The archive is created with owner-only permissions, and its
output path must be outside the library and must not already exist.

```sh
SONGBOOK_LIBRARY_ROOT=/path/to/library uv run songbook backup --output /path/to/private-backup.zip
uv run songbook restore --archive /path/to/private-backup.zip --destination /path/to/new-library --mode backup
SONGBOOK_LIBRARY_ROOT=/path/to/new-library uv run songbook reindex
```

The restore destination must not already exist; use a new path on the same
filesystem as its parent. Validation happens in a private staging directory
and publication uses a no-replace atomic rename on macOS and Linux. Other
platforms fail closed. The original library is never merged or overwritten.
Restore checks archive paths, file types, sizes, hashes, schema, relationships
and canonical revisions, migrates the staged database and rebuilds search.
Sessions are removed. Queued and in-flight imports and PDF jobs are marked
failed for manual review, so restored work does not automatically submit paid
requests. PDF artifacts are regenerated instead of backed up.

Operator environment variables, provider credentials and source-root mappings
are outside the managed library and must be reprovisioned separately; restore
does not trust machine-specific input paths. Secure backups as private data,
test restores periodically, and never publish them as static web content.

AI provider settings saved in the app (`.ai-provider.json`) are intentionally
excluded from both archive types, including their credentials and endpoint.
Re-enter them in Settings after restore, or protect and restore that owner-only
file separately. It is not encrypted; do not include it in portable music exports.
