"""Local resource limits, health, and container packaging contracts."""

import io
from pathlib import Path

from fastapi.testclient import TestClient

from server.songbook.config import Settings
from server.songbook.main import create_app
from server.songbook.storage.db import connect


def client_for(tmp_path):
    app = create_app(
        Settings(
            library_root=tmp_path / "library",
            source_roots={"offline": tmp_path / "missing"},
            allowed_origins=("http://testserver",),
            worker_required=True,
        )
    )
    app.state.auth.set_password("synthetic test password")
    client = TestClient(app, client=("127.0.0.1", 1234))
    login = client.post(
        "/api/session",
        json={"password": "synthetic test password"},
        headers={"Origin": "http://testserver"},
    )
    headers = {"Origin": "http://testserver", "X-CSRF-Token": login.json()["csrf"]}
    return app, client, headers


def test_oversized_upload_and_selection_are_rejected_without_jobs(tmp_path):
    app, client, headers = client_for(tmp_path)
    oversized = client.post(
        "/api/imports/sources?filename=huge.pdf",
        content=b"x" * (100 * 1024 * 1024 + 1),
        headers=headers,
    )
    assert oversized.status_code == 413 and oversized.json()["code"]
    source = app.state.store.register_source(
        io.BytesIO(b"synthetic"), "source.pdf", "pdf"
    )
    response = client.post(
        "/api/imports",
        json={
            "source_id": source.id,
            "selection": [{"pages": list(range(1, 22))}],
            "method": "local",
            "idempotency_key": "too-large",
        },
        headers=headers,
    )
    assert response.status_code == 400 and response.json()["code"]
    with connect(app.state.store.database) as db:
        assert db.execute("SELECT count(*) FROM import_jobs").fetchone()[0] == 0


def test_missing_optional_source_and_worker_do_not_hide_managed_original(tmp_path):
    app, client, _headers = client_for(tmp_path)
    source = app.state.store.register_source(
        io.BytesIO(b"synthetic"), "source.pdf", "pdf"
    )
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 503
    assert client.get(f"/api/sources/{source.id}/original").content == b"synthetic"
    assert client.get("/api/imports/scan/offline").status_code == 400


def test_container_build_declares_locked_dependencies_and_private_context():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text()
    ignore = (root / ".dockerignore").read_text()
    compose = (root / "compose.yaml").read_text()
    assert "npm ci" in dockerfile and "uv.lock" in dockerfile
    assert "PLAYWRIGHT_BROWSERS_PATH" in dockerfile and "USER " in dockerfile
    assert ".local" in ignore and ".env" in ignore and "songbook-data" in ignore
    optional = (root / "compose.sources.yaml").read_text()
    assert "127.0.0.1:" in compose and "read_only: true" in optional


def test_environment_can_require_worker_heartbeat(monkeypatch):
    from server.songbook.config import settings_from_environment

    monkeypatch.setenv("SONGBOOK_WORKER_REQUIRED", "true")
    assert settings_from_environment().worker_required is True


def test_worker_timeout_releases_capacity_for_next_job(tmp_path, monkeypatch):
    import subprocess

    from server.songbook.imports.jobs import ImportJobs
    from server.songbook.imports.worker import run_once
    from server.songbook.storage.arrangements import LibraryStore

    store = LibraryStore(tmp_path)
    source = store.register_source(
        io.BytesIO(b"{title: Synthetic}\n[C]Line"), "song.cho", "cho"
    )
    jobs = ImportJobs(store)
    first = jobs.enqueue_import(source.id, [{"pages": []}], "direct", "first")
    second = jobs.enqueue_import(source.id, [{"pages": []}], "direct", "second")
    process = jobs.process_direct

    def timeout_once(job_id, worker_id):
        if job_id == first["id"]:
            raise subprocess.TimeoutExpired("synthetic", 1)
        return process(job_id, worker_id)

    monkeypatch.setattr(jobs, "process_direct", timeout_once)
    assert run_once(jobs, "worker")
    assert jobs.get_job(first["id"])["state"] == "failed"
    assert run_once(jobs, "worker")
    assert jobs.get_job(second["id"])["state"] == "needs-review"
