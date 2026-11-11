"""Frozen PDF jobs, exact preview bytes and stale source conflicts."""

import hashlib

from fastapi.testclient import TestClient
from pypdf import PdfReader

from server.songbook.config import Settings
from server.songbook.main import create_app


def test_pdf_job_freezes_revision_and_preview_download_match(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    song = app.state.store.create_arrangement(
        None,
        "{title: PDF Test}\n{key: C}\n[C]Line one\n[C]Repeated chorus\n[C]Repeated chorus",
        [],
        None,
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/pdfs/forged").status_code == 401
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        body = {
            "arrangement_id": song.id,
            "revision": song.revision,
            "performance": {
                "semitones": 2,
                "spelling": "sharps",
                "capo": 0,
                "tuning": "high-g",
            },
            "settings": {
                "paper": "Letter",
                "fontPt": 12,
                "density": "compact",
                "marginsMm": 8,
                "columns": 1,
                "diagrams": False,
            },
        }
        queued = client.post("/api/pdfs", json=body, headers=headers)
        assert queued.status_code == 202
        job_id = queued.json()["id"]
        app.state.pdf_jobs.run_one("test-worker")
        status = client.get(f"/api/pdfs/{job_id}").json()
        assert status["state"] == "complete"
        downloaded = client.get(f"/api/pdfs/{job_id}/file")
        assert hashlib.sha256(downloaded.content).hexdigest() == status["sha256"]
        assert status["page_count"] == 1
        assert client.get(f"/api/pdfs/{job_id}/pages/1.png").content.startswith(
            b"\x89PNG"
        )
        from io import BytesIO

        reader = PdfReader(BytesIO(downloaded.content))
        assert float(reader.pages[0].mediabox.width) == 612
        text = " ".join(page.extract_text() for page in reader.pages)
        assert text.count("Repeated chorus") == 2
        assert "D" in text
        app.state.store.save_arrangement(song.id, song.revision, "[G]Changed")
        assert client.post("/api/pdfs", json=body, headers=headers).status_code == 409
        assert client.get(f"/api/pdfs/{job_id}/file").content == downloaded.content


def test_a4_artifact_keeps_frozen_content_when_source_changes(tmp_path):
    from io import BytesIO

    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    song = app.state.store.create_arrangement(
        None, "{title: Frozen}\n[C]Original content", [], None
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        body = {
            "arrangement_id": song.id,
            "revision": song.revision,
            "performance": {
                "semitones": 0,
                "spelling": "auto",
                "capo": 0,
                "tuning": "high-g",
            },
            "settings": {
                "paper": "A4",
                "fontPt": 14,
                "density": "compact",
                "marginsMm": 8,
                "columns": "auto",
                "diagrams": False,
            },
        }
        job = client.post("/api/pdfs", json=body, headers=headers).json()
        app.state.store.save_arrangement(
            song.id, song.revision, "{title: New}\n[D]Changed content"
        )
        app.state.pdf_jobs.run_one("worker")
        status = client.get(f"/api/pdfs/{job['id']}").json()
        assert status["state"] == "complete"
        assert status["renderer"]["browser_version"]
        assert len(status["renderer"]["font_hashes"]) == 2
        pdf = client.get(f"/api/pdfs/{job['id']}/file").content
        page = PdfReader(BytesIO(pdf)).pages[0]
        assert abs(float(page.mediabox.width) - 595.28) < 1
        assert "Original content" in page.extract_text()
        assert "Changed content" not in page.extract_text()


def test_infeasible_tab_has_visible_error(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    tab = "\n".join(string + "|" + "-" * 300 + "|" for string in "AECG")
    song = app.state.store.create_arrangement(
        None, "{title: Wide}\n{start_of_tab}\n" + tab + "\n{end_of_tab}", [], None
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        body = {
            "arrangement_id": song.id,
            "revision": song.revision,
            "performance": {
                "semitones": 0,
                "spelling": "auto",
                "capo": 0,
                "tuning": "high-g",
            },
            "settings": {
                "paper": "Letter",
                "fontPt": 20,
                "density": "compact",
                "marginsMm": 8,
                "columns": 1,
                "diagrams": False,
            },
        }
        job = client.post("/api/pdfs", json=body, headers=headers).json()
        app.state.pdf_jobs.run_one("worker")
        status = client.get(f"/api/pdfs/{job['id']}").json()
        assert status["state"] == "failed"
        assert status["error_code"] == "tab_too_wide"
        assert client.get(f"/api/pdfs/{job['id']}/file").status_code == 404


def test_oversized_tab_height_is_rejected_without_partial_pdf(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    tab = "\n".join("A|---|" for _ in range(150))
    song = app.state.store.create_arrangement(
        None, "{title: Tall}\n{start_of_tab}\n" + tab + "\n{end_of_tab}", [], None
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        body = {
            "arrangement_id": song.id,
            "revision": song.revision,
            "performance": {
                "semitones": 0,
                "spelling": "auto",
                "capo": 0,
                "tuning": "high-g",
            },
            "settings": {
                "paper": "Letter",
                "fontPt": 20,
                "density": "compact",
                "marginsMm": 8,
                "columns": 1,
                "diagrams": False,
            },
        }
        job = client.post("/api/pdfs", json=body, headers=headers).json()
        app.state.pdf_jobs.run_one("worker")
        status = client.get(f"/api/pdfs/{job['id']}").json()
        assert status["state"] == "failed" and status["error_code"] == "tab_too_tall"


def test_pdf_queue_is_bounded_before_starting_renderers(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    song = app.state.store.create_arrangement(None, "[C]Hello", [], None)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        body = {
            "arrangement_id": song.id,
            "revision": song.revision,
            "performance": {
                "semitones": 0,
                "spelling": "auto",
                "capo": 0,
                "tuning": "high-g",
            },
            "settings": {
                "paper": "Letter",
                "fontPt": 12,
                "density": "compact",
                "marginsMm": 8,
                "columns": 1,
                "diagrams": False,
            },
        }
        for _ in range(10):
            assert (
                client.post("/api/pdfs", json=body, headers=headers).status_code == 202
            )
        blocked = client.post("/api/pdfs", json=body, headers=headers)
        assert blocked.status_code == 429 and blocked.json()["retryable"] is True


def test_pdf_labels_source_shape_and_sounding_key(tmp_path):
    from io import BytesIO

    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    song = app.state.store.create_arrangement(
        None, "{title: Keys}\n{key: C}\n{capo: 2}\n[C]Music", [], None
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        body = {
            "arrangement_id": song.id,
            "revision": song.revision,
            "performance": {
                "semitones": 2,
                "spelling": "sharps",
                "capo": 2,
                "tuning": "high-g",
            },
            "settings": {
                "paper": "Letter",
                "fontPt": 12,
                "density": "compact",
                "marginsMm": 8,
                "columns": 1,
                "diagrams": False,
            },
        }
        job = client.post("/api/pdfs", json=body, headers=headers).json()
        app.state.pdf_jobs.run_one("worker")
        pdf = client.get(f"/api/pdfs/{job['id']}/file").content
        text = " ".join(
            page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages
        )
        assert (
            "Source key: C" in text
            and "shape key: D" in text
            and "sounding key: E" in text
            and "capo: 2" in text
        )
