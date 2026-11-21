"""Create a private archive from a consistent managed-library snapshot."""

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path

from ..storage.arrangements import LibraryStore, RecoveringError
from .manifest import (
    MAX_FILE,
    MAX_FILES,
    MAX_MANIFEST,
    MAX_TOTAL,
    VERSION,
    ExportManifest,
)


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _tables(db):
    return {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _sanitize(database: Path, portable: bool) -> None:
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA secure_delete=ON")
        tables = _tables(db)
        for table in ("sessions", "login_failures", "worker_heartbeat"):
            if table in tables:
                db.execute(f"DELETE FROM {table}")
        if portable and "auth_config" in tables:
            db.execute("DELETE FROM auth_config")
        if "codex_job_activity" in tables:
            db.execute("DELETE FROM codex_job_activity")
        if "import_jobs" in tables:
            if portable:
                allowed = {"pages", "rectangles", "paired_source_id", "paired_pages"}
                for ident, raw in db.execute(
                    "SELECT id,selection_json FROM import_jobs"
                ).fetchall():
                    selection = json.loads(raw)
                    if not isinstance(selection, list) or any(
                        not isinstance(part, dict) for part in selection
                    ):
                        raise ValueError("Invalid stored import selection")
                    cleaned = [
                        {key: value for key, value in part.items() if key in allowed}
                        for part in selection
                    ]
                    db.execute(
                        "UPDATE import_jobs SET selection_json=?,idempotency_key=? WHERE id=?",
                        (json.dumps(cleaned), "restored:" + ident, ident),
                    )
            db.execute(
                "UPDATE import_jobs SET state='failed',error_code='restore_requires_review',worker_id=NULL,lease_until=NULL WHERE state IN ('queued','processing')"
            )
        if "pdf_jobs" in tables:
            db.execute(
                "UPDATE pdf_jobs SET state='failed',error_code='restore_requires_review',worker_id=NULL,lease_until=NULL WHERE state IN ('queued','processing','complete')"
            )
        db.commit()
        db.execute("VACUUM")
        db.execute("PRAGMA journal_mode=DELETE")


def _snapshot(store: LibraryStore, staging: Path, portable: bool) -> None:
    # Recovery and the check under the lock together close the gap between
    # recovery and acquiring the snapshot lock. Never archive an active intent.
    store.recover_pending_writes()
    with store._lock():
        writer = sqlite3.connect(store.database, timeout=30)
        reader = sqlite3.connect(store.database, timeout=30)
        try:
            writer.execute("BEGIN IMMEDIATE")
            if writer.execute("SELECT 1 FROM write_intents LIMIT 1").fetchone():
                raise RecoveringError("Pending write requires recovery")
            with sqlite3.connect(staging / "library.sqlite") as copy:
                reader.backup(copy)
            total = (staging / "library.sqlite").stat().st_size
            count = 1
            if total > MAX_FILE or total > MAX_TOTAL:
                raise ValueError("Library exceeds archive limits")
            for dirname in ("arrangements", "sources", "assets", "derivatives"):
                root = store.root / dirname
                if not root.exists():
                    continue
                if root.is_symlink():
                    raise ValueError("Managed files contain a symlink")
                for directory, subdirs, files in os.walk(root, followlinks=False):
                    parent = Path(directory)
                    for name in subdirs + files:
                        if (parent / name).is_symlink():
                            raise ValueError("Managed files contain a symlink")
                    for name in files:
                        path = parent / name
                        if not path.is_file():
                            raise ValueError("Invalid managed file")
                        size = path.stat().st_size
                        total += size
                        count += 1
                        if size > MAX_FILE or total > MAX_TOTAL or count > MAX_FILES:
                            raise ValueError("Library exceeds archive limits")
                        target = staging / path.relative_to(store.root)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(path, target)
        finally:
            reader.close()
            writer.rollback()
            writer.close()
    _sanitize(staging / "library.sqlite", portable)


def _catalog(database: Path) -> dict[str, list[dict]]:
    # Only export explicitly selected application metadata; auth, sessions,
    # worker state and transient requests do not belong in the JSON catalog.
    queries = {
        "songs": "SELECT id FROM songs",
        "arrangements": "SELECT id,song_id,revision FROM arrangements",
        "arrangement_revisions": "SELECT arrangement_id,revision FROM arrangement_revisions",
        "revision_events": "SELECT id,arrangement_id,revision,created_at FROM revision_events",
        "sources": "SELECT id,sha256,original_name,kind,path FROM sources",
        "source_library_metadata": "SELECT source_id,revision,deleted FROM source_library_metadata",
        "arrangement_sources": "SELECT arrangement_id,source_id,pages_json,crop_asset_id FROM arrangement_sources",
        "assets": "SELECT id,sha256,path FROM assets",
        "library_metadata": "SELECT arrangement_id,revision,favorite,notes,last_played,deleted FROM library_metadata",
        "library_tags": "SELECT arrangement_id,tag FROM library_tags",
        "arrangement_preferences": "SELECT arrangement_id,document_json,etag FROM arrangement_preferences",
        "app_preferences": "SELECT id,document_json,etag FROM app_preferences",
        "setlists": "SELECT id,title,revision FROM setlists",
        "setlist_items": "SELECT id,setlist_id,arrangement_id,position FROM setlist_items",
        "setlist_tombstones": "SELECT id FROM setlist_tombstones",
        "import_jobs": "SELECT id,source_id,selection_json,method,state,created_at FROM import_jobs",
        "import_drafts": "SELECT id,job_id,ordinal,revision,pages_json,accepted_id FROM import_drafts",
        "import_draft_provenance": "SELECT draft_id,provider_json,provenance_json,uncertainty_json FROM import_draft_provenance",
    }
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        tables = _tables(db)
        result: dict[str, list[dict]] = {}
        total = 0
        for table, query in queries.items():
            if table not in tables:
                continue
            rows = result[table] = []
            for row in db.execute(query):
                item = dict(row)
                total += len(json.dumps(item, ensure_ascii=True).encode())
                if total > MAX_MANIFEST:
                    raise ValueError("Library catalog exceeds archive limits")
                rows.append(item)
        return result


def _archive(store: LibraryStore, destination: Path, mode: str) -> ExportManifest:
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Archive destination already exists")
    if destination.is_relative_to(store.root):
        raise ValueError("Archive destination must be outside the library")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".songbook-export-", dir=destination.parent
    ) as tmp:
        root = Path(tmp)
        snapshot = root / "snapshot"
        snapshot.mkdir()
        _snapshot(store, snapshot, mode == "portable")
        catalog = _catalog(snapshot / "library.sqlite")
        files = {}
        total = 0
        for path in sorted(snapshot.rglob("*")):
            if not path.is_file():
                continue
            size = path.stat().st_size
            total += size
            if size > MAX_FILE or total > MAX_TOTAL or len(files) >= MAX_FILES:
                raise ValueError("Library exceeds archive limits")
            files[path.relative_to(snapshot).as_posix()] = {
                "size": size,
                "sha256": _hash(path),
            }
        from .restore import _validate_database

        _validate_database(snapshot, files)
        manifest = ExportManifest(VERSION, mode, files, catalog)
        encoded_manifest = json.dumps(
            asdict(manifest), sort_keys=True, separators=(",", ":")
        ).encode()
        if len(encoded_manifest) > MAX_MANIFEST:
            raise ValueError("Library catalog exceeds archive limits")
        temporary = root / "archive.zip"
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as archive:
            archive.writestr("manifest.json", encoded_manifest)
            for name in files:
                archive.write(snapshot / name, "library/" + name)
        os.chmod(temporary, 0o600)
        # link is atomic and never replaces an existing destination.
        os.link(temporary, destination)
    return manifest


def export_library(store: LibraryStore, destination: Path) -> ExportManifest:
    return _archive(store, destination, "portable")


def export_arrangement(
    store: LibraryStore, ident: str, destination: Path, include_sources: bool
) -> ExportManifest:
    """Export an arrangement as ChordPro or a private bundle of related files."""
    import uuid

    ident = str(uuid.UUID(ident))
    destination = Path(destination).resolve()
    if destination.exists() or destination.is_relative_to(store.root):
        raise ValueError("Invalid arrangement export destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".songbook-arrangement-", dir=destination.parent
    ) as tmp:
        root = Path(tmp)
        snapshot = root / "snapshot"
        snapshot.mkdir()
        _snapshot(store, snapshot, True)
        catalog = _catalog(snapshot / "library.sqlite")
        arrangements = [row for row in catalog["arrangements"] if row["id"] == ident]
        if not arrangements:
            raise KeyError(ident)
        song_id = arrangements[0]["song_id"]
        source_name = f"arrangements/{ident}/song.chordpro"
        song_path = snapshot / source_name
        if not song_path.is_file() or _hash(song_path) != arrangements[0]["revision"]:
            raise ValueError("Arrangement unavailable or corrupt")
        temporary = root / "export"
        if not include_sources:
            shutil.copyfile(song_path, temporary)
            manifest = ExportManifest(
                VERSION,
                "chordpro",
                {
                    source_name: {
                        "size": song_path.stat().st_size,
                        "sha256": _hash(song_path),
                    }
                },
                {},
            )
        else:
            refs = [
                row
                for row in catalog["arrangement_sources"]
                if row["arrangement_id"] == ident
            ]
            source_ids = {row["source_id"] for row in refs}
            asset_ids = {row["crop_asset_id"] for row in refs if row["crop_asset_id"]}
            selected = {
                "songs": [row for row in catalog["songs"] if row["id"] == song_id],
                "arrangements": arrangements,
                "arrangement_revisions": [
                    row
                    for row in catalog["arrangement_revisions"]
                    if row["arrangement_id"] == ident
                ],
                "revision_events": [
                    row
                    for row in catalog["revision_events"]
                    if row["arrangement_id"] == ident
                ],
                "arrangement_sources": refs,
                "sources": [
                    row for row in catalog["sources"] if row["id"] in source_ids
                ],
                "assets": [row for row in catalog["assets"] if row["id"] in asset_ids],
                "library_metadata": [
                    row
                    for row in catalog.get("library_metadata", [])
                    if row["arrangement_id"] == ident
                ],
                "library_tags": [
                    row
                    for row in catalog.get("library_tags", [])
                    if row["arrangement_id"] == ident
                ],
                "arrangement_preferences": [
                    row
                    for row in catalog.get("arrangement_preferences", [])
                    if row["arrangement_id"] == ident
                ],
            }
            names = [source_name]
            names.extend(
                f"arrangements/{ident}/revisions/{row['revision']}.chordpro"
                for row in selected["arrangement_revisions"]
            )
            names.extend(
                row["path"] for row in selected["sources"] + selected["assets"]
            )
            files = {}
            for name in sorted(set(names)):
                path = snapshot / name
                if not path.is_file() or not path.resolve().is_relative_to(
                    snapshot.resolve()
                ):
                    raise ValueError("Related source unavailable")
                size = path.stat().st_size
                files[name] = {"size": size, "sha256": _hash(path)}
            if (
                len(files) > MAX_FILES
                or any(item["size"] > MAX_FILE for item in files.values())
                or sum(item["size"] for item in files.values()) > MAX_TOTAL
            ):
                raise ValueError("Arrangement exceeds archive limits")
            manifest = ExportManifest(VERSION, "arrangement", files, selected)
            encoded = json.dumps(
                asdict(manifest), sort_keys=True, separators=(",", ":")
            ).encode()
            if len(encoded) > MAX_MANIFEST:
                raise ValueError("Arrangement catalog exceeds archive limits")
            with zipfile.ZipFile(
                temporary, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
            ) as archive:
                archive.writestr("manifest.json", encoded)
                for name in files:
                    archive.write(snapshot / name, "library/" + name)
        os.chmod(temporary, 0o600)
        os.link(temporary, destination)
    return manifest
