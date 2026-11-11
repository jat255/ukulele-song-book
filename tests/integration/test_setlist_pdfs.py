"""Setlist PDFs retain ordered duplicate occurrences."""

import io
import uuid

from fastapi.testclient import TestClient
from pypdf import PdfReader

from server.songbook.config import Settings
from server.songbook.main import create_app


def test_set_pdf_preserves_occurrence_order_in_both_break_modes(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    first = app.state.store.create_arrangement(
        None, "{title: First}\n[C]Alpha", [], None
    )
    second = app.state.store.create_arrangement(
        None, "{title: Second}\n[G]Beta", [], None
    )
    playlist = app.state.setlists.create("Rehearsal")
    items = [
        {"id": str(uuid.uuid4()), "arrangementId": ident}
        for ident in (first.id, second.id, first.id)
    ]
    playlist = app.state.setlists.save_setlist(
        playlist["id"], playlist["revision"], "Rehearsal", items
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        settings = {
            "paper": "Letter",
            "fontPt": 12,
            "density": "compact",
            "marginsMm": 8,
            "columns": 1,
            "diagrams": False,
        }
        counts = {}
        for mode in ("new-page", "pack"):
            response = client.post(
                "/api/pdfs/setlist",
                json={
                    "setlist_id": playlist["id"],
                    "revision": playlist["revision"],
                    "settings": settings,
                    "songBreak": mode,
                },
                headers=headers,
            )
            assert response.status_code == 202
            job = response.json()
            app.state.pdf_jobs.run_one("worker")
            state = client.get(f"/api/pdfs/{job['id']}").json()
            assert state["state"] == "complete"
            reader = PdfReader(
                io.BytesIO(client.get(f"/api/pdfs/{job['id']}/file").content)
            )
            text = " ".join(page.extract_text() or "" for page in reader.pages)
            assert text.count("Alpha") == 2 and text.count("Beta") == 1
            assert text.index("Alpha") < text.index("Beta") < text.rindex("Alpha")
            counts[mode] = len(reader.pages)
        assert counts["new-page"] >= 3
        assert counts["pack"] < counts["new-page"]


def test_repeated_occurrences_freeze_same_source_and_performance(tmp_path, monkeypatch):
    import json

    from server.songbook.api import preferences
    from server.songbook.storage.db import connect

    app = create_app(Settings(library_root=tmp_path))
    song = app.state.store.create_arrangement(
        None, "{title: Repeat}\n[C]Line", [], None
    )
    playlist = app.state.setlists.create("Repeat")
    playlist = app.state.setlists.save_setlist(
        playlist["id"],
        playlist["revision"],
        "Repeat",
        [{"id": str(uuid.uuid4()), "arrangementId": song.id} for _ in range(2)],
    )
    original = preferences.read
    calls = 0

    def changing_preferences(db, ident):
        nonlocal calls
        raw, etag = original(db, ident)
        data = json.loads(raw)
        calls += 1
        data["groups"]["performance"]["value"]["semitones"] = calls
        return json.dumps(data), etag

    monkeypatch.setattr(preferences, "read", changing_preferences)
    job = app.state.pdf_jobs.enqueue_setlist(
        app.state.setlists, playlist["id"], playlist["revision"], {}, "pack"
    )
    with connect(app.state.store.database) as db:
        payload = json.loads(
            db.execute(
                "SELECT payload_json FROM pdf_jobs WHERE id=?", (job["id"],)
            ).fetchone()[0]
        )
    assert payload["performances"][0] == payload["performances"][1]
    assert payload["snapshots"][0]["revision"] == payload["snapshots"][1]["revision"]


def test_set_pdfs_preserve_long_sections_and_tab_on_letter_and_a4(tmp_path):
    app = create_app(Settings(library_root=tmp_path))
    first = app.state.store.create_arrangement(
        None,
        "{title: Long Song}\n{start_of_verse}\n"
        + "\n".join(f"[C]Section line {n:03}" for n in range(80))
        + "\n{end_of_verse}\n{start_of_tab}\nA|--0--|\nE|--1--|\nC|--0--|\nG|--2--|\n{end_of_tab}",
        [],
        None,
    )
    second = app.state.store.create_arrangement(
        None, "{title: Short Song}\n[G]Short ending", [], None
    )
    playlist = app.state.setlists.create("Mixed")
    playlist = app.state.setlists.save_setlist(
        playlist["id"],
        playlist["revision"],
        "Mixed",
        [
            {"id": str(uuid.uuid4()), "arrangementId": ident}
            for ident in (first.id, second.id, first.id)
        ],
    )
    for paper in ("Letter", "A4"):
        for mode in ("new-page", "pack"):
            job = app.state.pdf_jobs.enqueue_setlist(
                app.state.setlists,
                playlist["id"],
                playlist["revision"],
                {
                    "paper": paper,
                    "font_pt": 12,
                    "density": "compact",
                    "margins_mm": 8,
                    "columns": 1,
                    "diagrams": False,
                },
                mode,
            )
            app.state.pdf_jobs.run_one("worker")
            result = app.state.pdf_jobs.get(job["id"])
            assert result["state"] == "complete", result
            _, path = app.state.pdf_jobs.artifact(job["id"])
            reader = PdfReader(path)
            text = " ".join(page.extract_text() or "" for page in reader.pages)
            assert text.count("Section line 000") == 2
            assert text.count("Section line 079") == 2
            assert text.count("Short ending") == 1
            assert text.count("A|--0--|") == 2
            assert (
                text.index("Section line 079")
                < text.index("Short ending")
                < text.rindex("Section line 000")
            )
            assert len(reader.pages) == result["page_count"]
            print(f"{paper} {mode}: {len(reader.pages)} pages")


def test_set_pdf_rejects_stale_or_unavailable_occurrences_and_freezes_source(tmp_path):
    import pytest

    from server.songbook.storage.arrangements import ConflictError
    from server.songbook.storage.library import LibraryIndex

    app = create_app(Settings(library_root=tmp_path))
    song = app.state.store.create_arrangement(
        None, "{title: Frozen}\n[C]Before", [], None
    )
    playlist = app.state.setlists.create("Set")
    playlist = app.state.setlists.save_setlist(
        playlist["id"],
        playlist["revision"],
        "Set",
        [{"id": str(uuid.uuid4()), "arrangementId": song.id}],
    )
    settings = {
        "paper": "Letter",
        "font_pt": 12,
        "density": "compact",
        "margins_mm": 8,
        "columns": 1,
        "diagrams": False,
    }
    with pytest.raises(ConflictError):
        app.state.pdf_jobs.enqueue_setlist(
            app.state.setlists, playlist["id"], "stale", settings, "pack"
        )
    job = app.state.pdf_jobs.enqueue_setlist(
        app.state.setlists, playlist["id"], playlist["revision"], settings, "pack"
    )
    app.state.store.save_arrangement(
        song.id, song.revision, "{title: Frozen}\n[C]After"
    )
    app.state.pdf_jobs.run_one("worker")
    _, path = app.state.pdf_jobs.artifact(job["id"])
    text = " ".join(page.extract_text() or "" for page in PdfReader(path).pages)
    assert "Before" in text and "After" not in text
    library = LibraryIndex(app.state.store)
    library.delete(song.id, library.metadata(song.id)["revision"])
    with pytest.raises(ConflictError):
        app.state.pdf_jobs.enqueue_setlist(
            app.state.setlists, playlist["id"], playlist["revision"], settings, "pack"
        )


def test_set_pdf_freezes_preferences_across_concurrent_update(tmp_path, monkeypatch):
    import json
    import threading

    from server.songbook.api import preferences
    from server.songbook.storage.db import connect

    app = create_app(Settings(library_root=tmp_path))
    songs = [
        app.state.store.create_arrangement(
            None, f"{{title: {name}}}\n[C]Line", [], None
        )
        for name in ("One", "Two")
    ]
    playlist = app.state.setlists.create("Set")
    playlist = app.state.setlists.save_setlist(
        playlist["id"],
        playlist["revision"],
        "Set",
        [{"id": str(uuid.uuid4()), "arrangementId": song.id} for song in songs],
    )
    original = preferences.read
    updated = threading.Event()
    threads = []

    def update_defaults():
        with connect(app.state.store.database) as db:
            raw, _ = original(db, "defaults")
            data = json.loads(raw)
            data["groups"]["performance"]["value"]["semitones"] = 5
            encoded, etag = preferences.encode(
                preferences.Preferences.model_validate(data)
            )
            db.execute(
                "INSERT INTO app_preferences VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET document_json=excluded.document_json,etag=excluded.etag",
                (encoded, etag),
            )
        updated.set()

    def concurrent_read(db, ident):
        result = original(db, ident)
        if not threads:
            thread = threading.Thread(target=update_defaults)
            threads.append(thread)
            thread.start()
            updated.wait(0.5)
        return result

    monkeypatch.setattr(preferences, "read", concurrent_read)
    job = app.state.pdf_jobs.enqueue_setlist(
        app.state.setlists, playlist["id"], playlist["revision"], {}, "pack"
    )
    threads[0].join(timeout=5)
    assert updated.is_set()
    with connect(app.state.store.database) as db:
        payload = json.loads(
            db.execute(
                "SELECT payload_json FROM pdf_jobs WHERE id=?", (job["id"],)
            ).fetchone()[0]
        )
    assert [p["semitones"] for p in payload["performances"]] == [0, 0]


def test_set_pdf_reports_occurrence_limit(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    song = app.state.store.create_arrangement(None, "[C]Line", [], None)
    playlist = app.state.setlists.create("Large")
    playlist = app.state.setlists.save_setlist(
        playlist["id"],
        playlist["revision"],
        "Large",
        [{"id": str(uuid.uuid4()), "arrangementId": song.id} for _ in range(51)],
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        response = client.post(
            "/api/pdfs/setlist",
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": auth.json()["csrf"],
            },
            json={
                "setlist_id": playlist["id"],
                "revision": playlist["revision"],
                "settings": {
                    "paper": "Letter",
                    "fontPt": 12,
                    "density": "compact",
                    "marginsMm": 8,
                    "columns": 1,
                    "diagrams": False,
                },
            },
        )
        assert response.status_code == 400
        assert "50" in response.json()["message"]
