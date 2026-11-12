"""Portable archives preserve managed content without credentials."""

import io
import zipfile

from server.songbook.api.auth import AuthService
from server.songbook.portability.export import export_library
from server.songbook.portability.restore import restore_archive
from server.songbook.storage.arrangements import LibraryStore
from server.songbook.storage.db import connect


def test_portable_roundtrip_preserves_revisions_and_omits_auth(tmp_path):
    store = LibraryStore(tmp_path / "original")
    auth = AuthService(store.database, 3600)
    auth.set_password("synthetic-secret-password")
    token, csrf = auth.authenticate("synthetic-secret-password", "test")
    with connect(store.database) as db:
        password_hash = db.execute("SELECT password_hash FROM auth_config").fetchone()[
            0
        ]
    source = store.register_source(io.BytesIO(b"synthetic original"), "test.pdf", "pdf")
    first = store.create_arrangement(
        None,
        "{title: Example}\n[C]First",
        [{"source_id": source.id, "pages": [1]}],
        None,
    )
    current = store.save_arrangement(
        first.id, first.revision, "{title: Example}\n[G]Second\n{unknown: kept}"
    )
    archive = tmp_path / "portable.zip"
    export_library(store, archive)
    with zipfile.ZipFile(archive) as zipped:
        assert not any(
            "auth" in name or "session" in name for name in zipped.namelist()
        )
        contents = b"".join(zipped.read(name) for name in zipped.namelist())
        for secret in ("synthetic-secret-password", token, csrf, password_hash):
            assert secret.encode() not in contents
    restore_archive(archive, tmp_path / "restored", "portable")
    restored = LibraryStore(tmp_path / "restored")
    assert restored.get_arrangement(first.id).source == current.source
    assert restored.revision_path(first.id, first.revision).read_text() == first.source
    assert (
        restored.root / source.path.relative_to(store.root)
    ).read_bytes() == b"synthetic original"
    with connect(restored.database) as db:
        assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM auth_config").fetchone()[0] == 0


def test_backup_quiesces_file_and_database_writers_and_preserves_order(
    tmp_path, monkeypatch
):
    import threading
    import uuid
    from concurrent.futures import ThreadPoolExecutor

    from server.songbook.portability import export
    from server.songbook.portability.backup import backup_library
    from server.songbook.storage.library import LibraryIndex
    from server.songbook.storage.setlists import SetlistStore

    store = LibraryStore(tmp_path / "original")
    song = store.create_arrangement(None, "{title: Before}\n[C]One", [], None)
    index = LibraryIndex(store)
    metadata = index.metadata(song.id)
    index.update_metadata(
        song.id,
        metadata["revision"],
        favorite=True,
        tags=["practice"],
        notes="synthetic note",
    )
    sets = SetlistStore(store)
    playlist = sets.create("Set")
    items = [{"id": str(uuid.uuid4()), "arrangementId": song.id} for _ in range(2)]
    playlist = sets.save_setlist(playlist["id"], playlist["revision"], "Set", items)
    entered = threading.Event()
    proceed = threading.Event()
    original_copy = export.shutil.copyfile

    def paused_copy(source, target):
        entered.set()
        assert proceed.wait(5)
        return original_copy(source, target)

    monkeypatch.setattr(export.shutil, "copyfile", paused_copy)
    archive = tmp_path / "backup.zip"
    with ThreadPoolExecutor(max_workers=3) as pool:
        backup = pool.submit(backup_library, store, archive)
        assert entered.wait(5)
        edit = pool.submit(
            store.save_arrangement, song.id, song.revision, "{title: After}\n[G]Two"
        )
        change_set = pool.submit(
            sets.save_setlist,
            playlist["id"],
            playlist["revision"],
            "Changed",
            items[::-1],
        )
        assert not edit.done() and not change_set.done()
        proceed.set()
        backup.result(timeout=10)
        edit.result(timeout=10)
        change_set.result(timeout=10)
    restore_archive(archive, tmp_path / "restored", "backup")
    restored = LibraryStore(tmp_path / "restored")
    assert restored.get_arrangement(song.id).source == song.source
    assert LibraryIndex(restored).metadata(song.id)["tags"] == ["practice"]
    assert LibraryIndex(restored).metadata(song.id)["notes"] == "synthetic note"
    assert [
        item["id"] for item in SetlistStore(restored).get(playlist["id"])["items"]
    ] == [item["id"] for item in items]


def test_portable_manifest_contains_relationships_metadata_and_no_credentials(tmp_path):
    import json
    import uuid

    from server.songbook.storage.library import LibraryIndex
    from server.songbook.storage.setlists import SetlistStore

    store = LibraryStore(tmp_path / "original")
    song = store.create_arrangement(None, "{title: Example}\n[C]Song", [], None)
    library = LibraryIndex(store)
    library.update_metadata(
        song.id,
        library.metadata(song.id)["revision"],
        favorite=True,
        tags=["practice"],
        notes="work on rhythm",
    )
    sets = SetlistStore(store)
    playlist = sets.create("Evening")
    item = {"id": str(uuid.uuid4()), "arrangementId": song.id}
    sets.save_setlist(playlist["id"], playlist["revision"], "Evening", [item])
    archive = tmp_path / "portable.zip"
    export_library(store, archive)
    with zipfile.ZipFile(archive) as zipped:
        manifest = json.loads(zipped.read("manifest.json"))
    catalog = manifest["catalog"]
    assert any(
        row["id"] == song.id and row["song_id"] == song.song_id
        for row in catalog["arrangements"]
    )
    assert any(
        row["arrangement_id"] == song.id and row["notes"] == "work on rhythm"
        for row in catalog["library_metadata"]
    )
    assert any(
        row["id"] == item["id"] and row["arrangement_id"] == song.id
        for row in catalog["setlist_items"]
    )
    assert "auth_config" not in catalog and "sessions" not in catalog


def test_portable_scrubs_unrecognized_job_fields_and_does_not_restart_ai(tmp_path):
    import json
    import sqlite3
    import uuid

    from server.songbook.imports.jobs import ImportJobs
    from server.songbook.portability.backup import backup_library

    store = LibraryStore(tmp_path / "original")
    source = store.register_source(io.BytesIO(b"original"), "test.pdf", "pdf")
    ImportJobs(store)
    job = str(uuid.uuid4())
    selection = [
        {
            "pages": [1],
            "authorization": True,
            "provider": "synthetic",
            "model": "test",
            "machine_path": "/private/path/secret",
            "api_key": "synthetic-api-secret",
        }
    ]
    with connect(store.database) as db:
        db.execute(
            "INSERT INTO import_jobs (id,source_id,selection_json,method,idempotency_key,state,worker_id,lease_until,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                job,
                source.id,
                json.dumps(selection),
                "ai",
                "job",
                "processing",
                "worker",
                9999999999,
                0,
            ),
        )
    portable = tmp_path / "portable.zip"
    export_library(store, portable)
    with zipfile.ZipFile(portable) as zipped:
        payload = b"".join(zipped.read(name) for name in zipped.namelist())
        assert b"synthetic-api-secret" not in payload
        assert b"/private/path/secret" not in payload
    backup = tmp_path / "backup.zip"
    backup_library(store, backup)
    restore_archive(backup, tmp_path / "restored", "backup")
    with sqlite3.connect(tmp_path / "restored" / "library.sqlite") as db:
        state, worker, lease = db.execute(
            "SELECT state,worker_id,lease_until FROM import_jobs WHERE id=?", (job,)
        ).fetchone()
    assert state == "failed" and worker is None and lease is None


def test_backup_file_is_private(tmp_path):
    import stat

    from server.songbook.portability.backup import backup_library

    store = LibraryStore(tmp_path / "original")
    archive = tmp_path / "backup.zip"
    backup_library(store, archive)
    assert stat.S_IMODE(archive.stat().st_mode) == 0o600


def test_cli_export_backup_restore_and_reindex(tmp_path, monkeypatch):
    from server.songbook.cli import main

    root = tmp_path / "original"
    store = LibraryStore(root)
    song = store.create_arrangement(None, "{title: Example}\n[C]One", [], None)
    monkeypatch.setenv("SONGBOOK_LIBRARY_ROOT", str(root))
    portable = tmp_path / "portable.zip"
    backup = tmp_path / "backup.zip"
    restored = tmp_path / "restored"
    assert main(["export", "--output", str(portable)]) == 0
    assert main(["backup", "--output", str(backup)]) == 0
    assert (
        main(
            [
                "restore",
                "--archive",
                str(portable),
                "--destination",
                str(restored),
                "--mode",
                "portable",
            ]
        )
        == 0
    )
    monkeypatch.setenv("SONGBOOK_LIBRARY_ROOT", str(restored))
    assert main(["reindex"]) == 0
    assert LibraryStore(restored).get_arrangement(song.id).source == song.source


def test_arrangement_exports_preserve_source_without_exposing_other_songs(tmp_path):
    import json

    from server.songbook.portability.export import export_arrangement

    store = LibraryStore(tmp_path / "original")
    source = store.register_source(io.BytesIO(b"original"), "test.pdf", "pdf")
    song = store.create_arrangement(
        None,
        "{title: Selected}\n{define: X frets 0 1 2 3}\n{future: kept}\n[C]Song",
        [{"source_id": source.id, "pages": [1]}],
        None,
    )
    other = store.create_arrangement(
        None, "{title: Unrelated Secret}\n[Am]Other", [], None
    )
    plain = tmp_path / "song.chordpro"
    export_arrangement(store, song.id, plain, include_sources=False)
    assert plain.read_text() == song.source
    archive = tmp_path / "song.zip"
    export_arrangement(store, song.id, archive, include_sources=True)
    with zipfile.ZipFile(archive) as zipped:
        manifest = json.loads(zipped.read("manifest.json"))
        assert manifest["mode"] == "arrangement"
        assert (
            zipped.read("library/" + str(source.path.relative_to(store.root)))
            == b"original"
        )
        assert all(other.id not in name for name in zipped.namelist())
        assert b"Unrelated Secret" not in b"".join(
            zipped.read(name) for name in zipped.namelist()
        )


def test_export_api_requires_auth_csrf_and_streams_private_archive(tmp_path):
    import time

    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.main import create_app

    app = create_app(
        Settings(
            library_root=tmp_path / "library", allowed_origins=("http://testserver",)
        )
    )
    app.state.auth.set_password("synthetic test password")
    song = app.state.store.create_arrangement(
        None, "{title: API Test}\n[C]Song", [], None
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.post("/api/exports", json={"kind": "library"}).status_code == 401
        login = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        assert client.post("/api/exports", json={"kind": "library"}).status_code == 403
        headers = {"Origin": "http://testserver", "X-CSRF-Token": login.json()["csrf"]}
        for request in (
            {"kind": "library"},
            {"kind": "chordpro", "arrangement_id": song.id},
            {"kind": "arrangement", "arrangement_id": song.id},
        ):
            created = client.post("/api/exports", json=request, headers=headers)
            assert created.status_code == 202
            ident = created.json()["id"]
            for _ in range(100):
                result = client.get(f"/api/exports/{ident}").json()
                if result["state"] != "pending":
                    break
                time.sleep(0.02)
            assert result["state"] == "complete", request
            download = client.get(f"/api/exports/{ident}/file")
            assert (
                download.status_code == 200
                and download.headers["cache-control"] == "no-store"
            )
            assert download.content.startswith(
                b"{title: API Test}" if request["kind"] == "chordpro" else b"PK"
            )


def test_export_rejects_destination_inside_library_via_symlink(tmp_path):
    import pytest

    store = LibraryStore(tmp_path / "original")
    alias = tmp_path / "alias"
    alias.symlink_to(store.root, target_is_directory=True)
    with pytest.raises(ValueError):
        export_library(store, alias / "not-allowed.zip")
    assert not (store.root / "not-allowed.zip").exists()


def test_completed_export_jobs_are_evicted_to_make_room(tmp_path):
    import time

    from server.songbook.api.exports import ExportJobs, ExportRequest

    store = LibraryStore(tmp_path / "original")
    jobs = ExportJobs(store)
    first = None
    for _ in range(6):
        job = jobs.create(ExportRequest(kind="library"), "owner")
        first = first or job["id"]
        for _ in range(200):
            if jobs.get(job["id"], "owner")["state"] != "pending":
                break
            time.sleep(0.01)
        assert jobs.get(job["id"], "owner")["state"] == "complete"
    import pytest

    with pytest.raises(KeyError):
        jobs.get(first, "owner")


def test_clean_backup_restore_can_login_search_open_original_and_render_pdf(tmp_path):
    from io import BytesIO

    from fastapi.testclient import TestClient
    from pypdf import PdfReader

    from server.songbook.config import Settings
    from server.songbook.main import create_app
    from server.songbook.pdf.models import PdfRenderRequest
    from server.songbook.pdf.render import render_pdf
    from server.songbook.portability.backup import backup_library
    from server.songbook.storage.library import LibraryIndex

    app = create_app(
        Settings(
            library_root=tmp_path / "original", allowed_origins=("http://testserver",)
        )
    )
    app.state.auth.set_password("synthetic test password")
    source = app.state.store.register_source(
        io.BytesIO(b"synthetic original"), "synthetic.pdf", "pdf"
    )
    song = app.state.store.create_arrangement(
        None,
        "{title: Restored Song}\n[C]Synthetic words\n{start_of_tab}\nA|--0--|\nE|--0--|\nC|--0--|\nG|--0--|\n{end_of_tab}",
        [{"source_id": source.id, "pages": [1]}],
        None,
    )
    backup = tmp_path / "backup.zip"
    backup_library(app.state.store, backup)
    destination = tmp_path / "restored"
    restore_archive(backup, destination, "backup")
    restored_app = create_app(
        Settings(library_root=destination, allowed_origins=("http://testserver",))
    )
    with TestClient(restored_app, client=("127.0.0.1", 1234)) as client:
        login = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        assert login.status_code == 200
        assert (
            client.get(f"/api/sources/{source.id}/original").content
            == b"synthetic original"
        )
    assert (
        LibraryIndex(restored_app.state.store).search_library("Restored", [], False)[0][
            "id"
        ]
        == song.id
    )
    snapshot = restored_app.state.store.get_arrangement(song.id)
    artifact = render_pdf(
        PdfRenderRequest(source=snapshot.source, output_dir=tmp_path / "pdf", columns=1)
    )
    reader = PdfReader(BytesIO(artifact.path.read_bytes()))
    assert len(reader.pages) == 1
    assert "Synthetic words" in reader.pages[0].extract_text()


def test_backup_refuses_a_corrupt_managed_original(tmp_path):
    import pytest

    from server.songbook.portability.backup import backup_library

    store = LibraryStore(tmp_path / "original")
    source = store.register_source(io.BytesIO(b"original"), "source.pdf", "pdf")
    source.path.write_bytes(b"corrupt")
    archive = tmp_path / "backup.zip"
    with pytest.raises(ValueError):
        backup_library(store, archive)
    assert not archive.exists()


def test_portable_roundtrip_variants_shared_pages_preferences_and_setlist(tmp_path):
    import json
    import uuid

    from server.songbook.api.preferences import Preferences, encode, initialize
    from server.songbook.storage.library import LibraryIndex
    from server.songbook.storage.setlists import SetlistStore

    store = LibraryStore(tmp_path / "original")
    source = store.register_source(
        io.BytesIO(b"synthetic shared book"), "book.pdf", "pdf"
    )
    first = store.create_arrangement(
        None,
        "{title: Synthetic}\n{future: preserve}\n[C]First",
        [{"source_id": source.id, "pages": [2]}],
        None,
    )
    variant = store.create_arrangement(
        first.song_id,
        "{title: Synthetic variant}\n{start_of_tab}\nA|--0--|\nE|--0--|\nC|--0--|\nG|--0--|\n{end_of_tab}",
        [{"source_id": source.id, "pages": [3]}],
        None,
    )
    LibraryIndex(store)
    initialize(store.database)
    preferences = Preferences()
    preferences.groups.performance.value.capo = 3
    raw, etag = encode(preferences)
    with connect(store.database) as db:
        db.execute(
            "INSERT INTO arrangement_preferences VALUES (?,?,?)",
            (variant.id, raw, etag),
        )
    sets = SetlistStore(store)
    playlist = sets.create("Synthetic set")
    items = [
        {"id": str(uuid.uuid4()), "arrangementId": ident}
        for ident in (first.id, variant.id, first.id)
    ]
    saved = sets.save_setlist(
        playlist["id"], playlist["revision"], "Synthetic set", items
    )
    archive = tmp_path / "portable.zip"
    export_library(store, archive)
    restore_archive(archive, tmp_path / "restored", "portable")
    restored = LibraryStore(tmp_path / "restored")
    assert restored.get_arrangement(variant.id).song_id == first.song_id
    assert restored.get_arrangement(variant.id).source == variant.source
    assert restored.get_arrangement(first.id).source_refs[0]["pages"] == [2]
    assert restored.get_arrangement(variant.id).source_refs[0]["pages"] == [3]
    assert [
        item["id"] for item in SetlistStore(restored).get(saved["id"])["items"]
    ] == [item["id"] for item in items]
    with connect(restored.database) as db:
        saved_preferences = json.loads(
            db.execute(
                "SELECT document_json FROM arrangement_preferences WHERE arrangement_id=?",
                (variant.id,),
            ).fetchone()[0]
        )
    assert saved_preferences["groups"]["performance"]["value"]["capo"] == 3


def test_standalone_chordpro_opens_in_independent_chordpro(tmp_path):
    import shutil
    import subprocess

    import pytest

    from server.songbook.portability.export import export_arrangement

    tool = shutil.which("chordpro")
    if not tool:
        pytest.skip("Independent ChordPro executable unavailable")
    store = LibraryStore(tmp_path / "source")
    song = store.create_arrangement(
        None,
        "{title: Synthetic}\n{define: X frets 0 1 2 3}\n[C]Synthetic line",
        [],
        None,
    )
    standalone = tmp_path / "song.chordpro"
    export_arrangement(store, song.id, standalone, False)
    result = subprocess.run(
        [tool, "--output", str(tmp_path / "independent.pdf"), str(standalone)],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
    assert (tmp_path / "independent.pdf").read_bytes().startswith(b"%PDF")


def test_backup_recovers_an_interrupted_arrangement_write(tmp_path):
    import pytest

    from server.songbook.portability.backup import backup_library

    store = LibraryStore(tmp_path / "source")
    first = store.create_arrangement(None, "[C]Before", [], None)

    def crash(stage):
        if stage == "after_revision":
            raise RuntimeError("simulated crash")

    store.crash_hook = crash
    with pytest.raises(RuntimeError):
        store.save_arrangement(first.id, first.revision, "[G]Recovered")
    store.crash_hook = lambda stage: None
    archive = tmp_path / "backup.zip"
    backup_library(store, archive)
    restore_archive(archive, tmp_path / "restored", "backup")
    assert (
        LibraryStore(tmp_path / "restored").get_arrangement(first.id).source
        == "[G]Recovered"
    )


def test_snapshot_checks_size_before_copying_large_managed_files(tmp_path, monkeypatch):
    import pytest

    from server.songbook.portability import export

    store = LibraryStore(tmp_path / "source")
    store.register_source(io.BytesIO(b"synthetic original"), "source.pdf", "pdf")
    monkeypatch.setattr(export, "MAX_FILE", 3)

    def unexpected_copy(*args, **kwargs):
        raise AssertionError("oversized content was copied")

    monkeypatch.setattr(export.shutil, "copyfile", unexpected_copy)
    with pytest.raises(ValueError):
        export_library(store, tmp_path / "archive.zip")


def test_catalog_limit_is_enforced_while_reading_rows(tmp_path, monkeypatch):
    import pytest

    from server.songbook.portability import export
    from server.songbook.storage.library import LibraryIndex

    store = LibraryStore(tmp_path / "source")
    song = store.create_arrangement(None, "{title: Synthetic}\n[C]Song", [], None)
    library = LibraryIndex(store)
    library.update_metadata(
        song.id,
        library.metadata(song.id)["revision"],
        favorite=False,
        tags=[],
        notes="x" * 5000,
    )
    monkeypatch.setattr(export, "MAX_MANIFEST", 1000)
    with pytest.raises(ValueError):
        export._catalog(store.database)
