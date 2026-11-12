# Portable exports

The library screen can prepare a private complete library archive, or export an
individual arrangement as ChordPro or as a bundle with its related originals
and revision history. An export is prepared in the background; the download
link is available to the same signed-in browser session for up to one hour.
Export jobs are temporary and do not survive a server restart. Only one export
is prepared at a time. The five most recent completed jobs are retained.

A local operator can also run:

```sh
uv run songbook export --output /path/outside/library/songbook.zip
uv run songbook restore --archive /path/outside/library/songbook.zip --destination /path/to/new-library --mode portable
```

Set `SONGBOOK_LIBRARY_ROOT` to the managed library before exporting. The
versioned JSON manifest includes hashes, relative managed-file paths, stable
IDs, relationships and application metadata. The archive contains canonical
files, retained originals, revisions, and a SQLite snapshot. Portable archives
omit password hashes and sessions; provision a new password after restore.
The standalone ChordPro preserves unknown directives and embedded definitions;
it does not transpose tablature. The arrangement bundle is an export for
inspection and transfer, not a complete library restore archive.

Exports contain private songs, originals, notes and metadata. Protect the files
and share them only deliberately. The archive format validates checksums, not
identity: it does not prove who created a file. External provider credentials,
source-root paths and other operator environment settings must be configured
separately. PDF extraction drafts are review-only.
