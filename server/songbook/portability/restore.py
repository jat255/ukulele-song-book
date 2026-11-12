"""Validate an archive completely before publishing a separate library."""

import ctypes
import errno
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Literal

from .manifest import (
    MAX_FILE,
    MAX_FILES,
    MAX_MANIFEST,
    MAX_TOTAL,
    VERSION,
    RestoreReport,
)


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and "\\" not in name
        and not path.is_absolute()
        and all(part not in ("", ".", "..") for part in name.split("/"))
    )


def _publish(source: Path, destination: Path) -> None:
    # Both supported local platforms provide an atomic no-replace rename.
    # Fail closed on other platforms rather than overwrite a raced destination.
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes, destination_bytes = os.fsencode(source), os.fsencode(destination)
    if sys.platform == "darwin":
        operation = libc.renamex_np
        operation.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = operation(source_bytes, destination_bytes, 0x4)  # RENAME_EXCL
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        operation = libc.renameat2
        operation.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        result = operation(
            -100, source_bytes, -100, destination_bytes, 1
        )  # RENAME_NOREPLACE
    else:
        raise ValueError("Atomic restore publication is unavailable on this platform")
    if result:
        error = ctypes.get_errno()
        if error in (errno.EEXIST, errno.ENOTEMPTY):
            raise ValueError("Destination already exists")
        raise OSError(error, os.strerror(error))


def _validate_database(root: Path, files: dict) -> None:
    # Refuse arbitrary schemas, including triggers or attacker-supplied views,
    # before opening the restored database through application code.
    migrations = Path(__file__).parents[1] / "storage" / "migrations"
    with sqlite3.connect(":memory:") as template:
        for migration in sorted(migrations.glob("*.sql")):
            template.executescript(migration.read_text())
        template.execute(
            "CREATE TABLE IF NOT EXISTS vision_requests (identity TEXT PRIMARY KEY, state TEXT NOT NULL)"
        )
        expected = set(
            template.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        )
    with sqlite3.connect(root / "library.sqlite") as db:
        db.execute("PRAGMA trusted_schema=OFF")
        actual = set(
            db.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        )
        if not actual.issubset(expected):
            raise ValueError("Unsupported database schema")
        if (
            db.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            or db.execute("PRAGMA foreign_key_check").fetchone() is not None
        ):
            raise ValueError("Invalid library database")
        versions = {
            row[0] for row in db.execute("SELECT version FROM schema_migrations")
        }
        known = {int(path.name.split("_", 1)[0]) for path in migrations.glob("*.sql")}
        if not versions or not versions.issubset(known):
            raise ValueError("Unsupported database version")
        if db.execute("SELECT 1 FROM write_intents LIMIT 1").fetchone():
            raise ValueError("Archive contains an unfinished write")
        for ident, revision in db.execute("SELECT id,revision FROM arrangements"):
            if (
                str(uuid.UUID(ident)) != ident
                or revision is None
                or not re.fullmatch("[0-9a-f]{64}", revision)
            ):
                raise ValueError("Invalid arrangement identity")
            name = f"arrangements/{ident}/song.chordpro"
            if files.get(name, {}).get("sha256") != revision:
                raise ValueError("Arrangement does not match its revision")
        for ident, revision in db.execute(
            "SELECT arrangement_id,revision FROM arrangement_revisions"
        ):
            if str(uuid.UUID(ident)) != ident or not re.fullmatch(
                "[0-9a-f]{64}", revision
            ):
                raise ValueError("Invalid revision identity")
            if (
                files.get(
                    f"arrangements/{ident}/revisions/{revision}.chordpro", {}
                ).get("sha256")
                != revision
            ):
                raise ValueError("Arrangement history is incomplete")
        for ident, digest, kind, name in db.execute(
            "SELECT id,sha256,kind,path FROM sources"
        ):
            if (
                str(uuid.UUID(ident)) != ident
                or kind not in ("pdf", "cho", "chordpro")
                or name != f"sources/{ident}/original.{kind}"
            ):
                raise ValueError("Invalid source path")
            if files.get(name, {}).get("sha256") != digest:
                raise ValueError("Source is missing or corrupt")
        for digest, name in db.execute("SELECT sha256,path FROM assets"):
            if (
                not _safe_name(name)
                or not name.startswith("assets/")
                or files.get(name, {}).get("sha256") != digest
            ):
                raise ValueError("Asset is missing or corrupt")


def restore_archive(
    archive: Path, destination: Path, mode: Literal["portable", "backup"]
) -> RestoreReport:
    if mode not in ("portable", "backup"):
        raise ValueError("Invalid archive mode")
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Destination must not already exist")
    if not destination.parent.is_dir():
        raise ValueError("Destination parent must exist")
    try:
        with (
            zipfile.ZipFile(archive) as zipped,
            tempfile.TemporaryDirectory(
                prefix=".songbook-restore-", dir=destination.parent
            ) as tmp,
        ):
            infos = zipped.infolist()
            if len(infos) > MAX_FILES + 1:
                raise ValueError("Too many archive entries")
            names = [item.filename for item in infos]
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise ValueError("Invalid archive directory")
            total = 0
            for item in infos:
                kind = stat.S_IFMT(item.external_attr >> 16)
                if (
                    not _safe_name(item.filename)
                    or item.is_dir()
                    or kind not in (0, stat.S_IFREG)
                ):
                    raise ValueError("Invalid archive entry")
                total += item.file_size
                if item.file_size > MAX_FILE or total > MAX_TOTAL:
                    raise ValueError("Archive exceeds size limit")
            manifest_info = zipped.getinfo("manifest.json")
            if manifest_info.file_size > MAX_MANIFEST:
                raise ValueError("Manifest exceeds size limit")
            manifest = json.loads(zipped.read(manifest_info))
            if (
                not isinstance(manifest, dict)
                or manifest.get("version") != VERSION
                or manifest.get("mode") != mode
                or not isinstance(manifest.get("files"), dict)
            ):
                raise ValueError("Unsupported archive manifest")
            files = manifest["files"]
            if (
                set(names) != {"manifest.json"} | {"library/" + name for name in files}
                or "library.sqlite" not in files
            ):
                raise ValueError("Archive entries do not match manifest")
            root = Path(tmp) / "library"
            root.mkdir(mode=0o700)
            for name, metadata in files.items():
                if (
                    not _safe_name(name)
                    or not isinstance(metadata, dict)
                    or (
                        name != "library.sqlite"
                        and name.split("/", 1)[0]
                        not in {"arrangements", "sources", "assets", "derivatives"}
                    )
                ):
                    raise ValueError("Invalid manifest file")
                size = metadata.get("size")
                digest = metadata.get("sha256")
                if (
                    type(size) is not int
                    or size < 0
                    or size > MAX_FILE
                    or not isinstance(digest, str)
                    or not re.fullmatch("[0-9a-f]{64}", digest)
                ):
                    raise ValueError("Invalid manifest checksum")
                info = zipped.getinfo("library/" + name)
                if info.file_size != size:
                    raise ValueError("Archive size mismatch")
                target = root.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                calculated = hashlib.sha256()
                written = 0
                with zipped.open(info) as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        written += len(chunk)
                        if written > size:
                            raise ValueError("Archive size mismatch")
                        calculated.update(chunk)
                        output.write(chunk)
                os.chmod(target, 0o600)
                if written != size or calculated.hexdigest() != digest:
                    raise ValueError("Archive checksum mismatch")
            _validate_database(root, files)
            from .export import _catalog, _sanitize

            if manifest.get("catalog") != _catalog(root / "library.sqlite"):
                raise ValueError("Catalog does not match library database")
            _sanitize(root / "library.sqlite", mode == "portable")
            from ..storage.arrangements import LibraryStore

            restored = LibraryStore(root)
            migrations = Path(__file__).parents[1] / "storage" / "migrations"
            with sqlite3.connect(restored.database) as db:
                for migration in sorted(migrations.glob("*.sql")):
                    db.executescript(migration.read_text())
                db.execute("DELETE FROM arrangement_search")
            restored.recover_pending_writes()
            if destination.exists() or destination.is_symlink():
                raise ValueError("Destination already exists")
            _publish(root, destination)
            return RestoreReport(mode, len(files))
    except (
        zipfile.BadZipFile,
        EOFError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        sqlite3.DatabaseError,
        OSError,
        KeyError,
        TypeError,
    ) as exc:
        raise ValueError("Invalid or unreadable archive") from exc
