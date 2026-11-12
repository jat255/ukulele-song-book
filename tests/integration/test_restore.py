"""Unsafe archives never change a destination or escape staging."""

import zipfile

import pytest

from server.songbook.portability.restore import restore_archive


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../../escape"])
def test_rejects_unsafe_archive_paths_without_changing_destination(tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(name, b"unsafe")
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "sentinel").write_text("unchanged")
    with pytest.raises(ValueError):
        restore_archive(archive, destination, "portable")
    assert list(destination.iterdir()) == [destination / "sentinel"]
    assert (destination / "sentinel").read_text() == "unchanged"
    with pytest.raises(ValueError):
        restore_archive(archive, tmp_path / "new-library", "portable")
    assert not (tmp_path / "new-library").exists()
    assert not (tmp_path / "escape").exists()


def test_rejects_tampered_and_unsupported_archives(tmp_path):
    import json

    from server.songbook.portability.export import export_library
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path / "original")
    store.create_arrangement(None, "{title: Example}\n[C]One", [], None)
    original = tmp_path / "original.zip"
    export_library(store, original)
    with zipfile.ZipFile(original) as zipped:
        entries = {item.filename: zipped.read(item) for item in zipped.infolist()}
    for variant in ("checksum", "version", "truncated", "symlink"):
        altered = dict(entries)
        manifest = json.loads(altered["manifest.json"])
        if variant == "checksum":
            name = next(name for name in altered if name.endswith("song.chordpro"))
            altered[name] = b"changed"
        if variant == "version":
            manifest["version"] = 999
            altered["manifest.json"] = json.dumps(manifest).encode()
        archive = tmp_path / f"{variant}.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            for name, data in altered.items():
                if variant == "symlink" and name.endswith("song.chordpro"):
                    info = zipfile.ZipInfo(name)
                    info.create_system = 3
                    info.external_attr = 0o120777 << 16
                    zipped.writestr(info, data)
                else:
                    zipped.writestr(name, data)
        if variant == "truncated":
            archive.write_bytes(archive.read_bytes()[:-20])
        destination = tmp_path / f"restored-{variant}"
        with pytest.raises(ValueError):
            restore_archive(archive, destination, "portable")
        assert not destination.exists()


def test_rejects_excessive_declared_expansion(tmp_path, monkeypatch):
    from server.songbook.portability import restore
    from server.songbook.portability.export import export_library
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path / "source")
    archive = tmp_path / "library.zip"
    export_library(store, archive)
    monkeypatch.setattr(restore, "MAX_TOTAL", 100)
    with pytest.raises(ValueError):
        restore_archive(archive, tmp_path / "destination", "portable")


def test_rejects_self_consistent_archive_with_corrupt_canonical_song(tmp_path):
    import hashlib
    import json

    from server.songbook.portability.export import export_library
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path / "source")
    store.create_arrangement(None, "{title: Example}\n[C]One", [], None)
    original = tmp_path / "source.zip"
    export_library(store, original)
    with zipfile.ZipFile(original) as zipped:
        entries = {item.filename: zipped.read(item) for item in zipped.infolist()}
    name = next(name for name in entries if name.endswith("song.chordpro"))
    entries[name] = b"not the recorded revision"
    manifest = json.loads(entries["manifest.json"])
    manifest["files"][name.removeprefix("library/")] = {
        "size": len(entries[name]),
        "sha256": hashlib.sha256(entries[name]).hexdigest(),
    }
    entries["manifest.json"] = json.dumps(manifest).encode()
    modified = tmp_path / "modified.zip"
    with zipfile.ZipFile(modified, "w") as zipped:
        for filename, data in entries.items():
            zipped.writestr(filename, data)
    with pytest.raises(ValueError):
        restore_archive(modified, tmp_path / "destination", "portable")
    assert not (tmp_path / "destination").exists()


def test_restored_library_is_private(tmp_path):
    import stat

    from server.songbook.portability.backup import backup_library
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path / "source")
    archive = tmp_path / "backup.zip"
    backup_library(store, archive)
    destination = tmp_path / "destination"
    restore_archive(archive, destination, "backup")
    assert stat.S_IMODE(destination.stat().st_mode) == 0o700
    assert stat.S_IMODE((destination / "library.sqlite").stat().st_mode) == 0o600


def test_publish_never_replaces_a_destination_created_during_restore(
    tmp_path, monkeypatch
):
    from server.songbook.portability import restore
    from server.songbook.portability.export import export_library
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path / "source")
    archive = tmp_path / "source.zip"
    export_library(store, archive)
    destination = tmp_path / "destination"
    original_publish = restore._publish

    def collide(source, target):
        target.mkdir()
        original_publish(source, target)

    monkeypatch.setattr(restore, "_publish", collide)
    with pytest.raises(ValueError):
        restore_archive(archive, destination, "portable")
    assert destination.is_dir() and not list(destination.iterdir())


def test_rejects_catalog_that_disagrees_with_database(tmp_path):
    import json

    from server.songbook.portability.export import export_library
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path / "source")
    store.create_arrangement(None, "[C]Song", [], None)
    original = tmp_path / "source.zip"
    export_library(store, original)
    with zipfile.ZipFile(original) as zipped:
        entries = {item.filename: zipped.read(item) for item in zipped.infolist()}
    manifest = json.loads(entries["manifest.json"])
    manifest["catalog"]["arrangements"] = []
    entries["manifest.json"] = json.dumps(manifest).encode()
    modified = tmp_path / "modified.zip"
    with zipfile.ZipFile(modified, "w") as zipped:
        for filename, data in entries.items():
            zipped.writestr(filename, data)
    with pytest.raises(ValueError):
        restore_archive(modified, tmp_path / "destination", "portable")
    assert not (tmp_path / "destination").exists()


def test_restore_clears_sessions_even_if_archive_contains_them(tmp_path):
    import hashlib
    import json
    import sqlite3

    from server.songbook.api.auth import AuthService
    from server.songbook.portability.backup import backup_library
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path / "source")
    AuthService(store.database, 3600)
    original = tmp_path / "backup.zip"
    backup_library(store, original)
    with zipfile.ZipFile(original) as zipped:
        entries = {item.filename: zipped.read(item) for item in zipped.infolist()}
    db_path = tmp_path / "altered.sqlite"
    db_path.write_bytes(entries["library/library.sqlite"])
    with sqlite3.connect(db_path) as db:
        db.execute("INSERT INTO sessions VALUES ('active', 'csrf', 99999999999)")
    entries["library/library.sqlite"] = db_path.read_bytes()
    manifest = json.loads(entries["manifest.json"])
    payload = entries["library/library.sqlite"]
    manifest["files"]["library.sqlite"] = {
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    entries["manifest.json"] = json.dumps(manifest).encode()
    modified = tmp_path / "modified.zip"
    with zipfile.ZipFile(modified, "w") as zipped:
        for name, data in entries.items():
            zipped.writestr(name, data)
    destination = tmp_path / "restored"
    restore_archive(modified, destination, "backup")
    with sqlite3.connect(destination / "library.sqlite") as db:
        assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0


@pytest.mark.parametrize("unexpected", ["library.sqlite-wal", "config.json"])
def test_rejects_unexpected_database_sidecars(tmp_path, unexpected):
    import hashlib
    import json

    from server.songbook.portability.export import export_library
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path / "source")
    original = tmp_path / "source.zip"
    export_library(store, original)
    with zipfile.ZipFile(original) as zipped:
        entries = {item.filename: zipped.read(item) for item in zipped.infolist()}
    payload = b"hostile sidecar"
    entries["library/" + unexpected] = payload
    manifest = json.loads(entries["manifest.json"])
    manifest["files"][unexpected] = {
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    entries["manifest.json"] = json.dumps(manifest).encode()
    modified = tmp_path / "modified.zip"
    with zipfile.ZipFile(modified, "w") as zipped:
        for name, data in entries.items():
            zipped.writestr(name, data)
    with pytest.raises(ValueError):
        restore_archive(modified, tmp_path / "destination", "portable")
    assert not (tmp_path / "destination").exists()


def test_restore_rejects_future_database_schema_version(tmp_path):
    import hashlib
    import json
    import sqlite3

    from server.songbook.portability.export import export_library
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path / "source")
    archive = tmp_path / "source.zip"
    export_library(store, archive)
    with zipfile.ZipFile(archive) as zipped:
        entries = {item.filename: zipped.read(item) for item in zipped.infolist()}
    database = tmp_path / "altered.sqlite"
    database.write_bytes(entries["library/library.sqlite"])
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO schema_migrations VALUES (999)")
    payload = database.read_bytes()
    entries["library/library.sqlite"] = payload
    manifest = json.loads(entries["manifest.json"])
    manifest["files"]["library.sqlite"] = {
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    entries["manifest.json"] = json.dumps(manifest).encode()
    altered = tmp_path / "altered.zip"
    with zipfile.ZipFile(altered, "w") as zipped:
        for name, data in entries.items():
            zipped.writestr(name, data)
    with pytest.raises(ValueError):
        restore_archive(altered, tmp_path / "destination", "portable")
