"""Durable import jobs and review acceptance."""

import io

import pytest

from server.songbook.imports.jobs import ImportJobs
from server.songbook.storage.arrangements import ConflictError, LibraryStore
from server.songbook.storage.db import connect


def setup_job(tmp_path):
    store = LibraryStore(tmp_path)
    source = store.register_source(
        io.BytesIO(b"{title: Synthetic}\n[C]Hello"), "test.cho", "cho"
    )
    jobs = ImportJobs(store)
    job = jobs.enqueue_import(source.id, [{"pages": []}], "direct", "test-key")
    return store, jobs, job


def test_restart_reclaims_expired_lease(tmp_path):
    _, jobs, job = setup_job(tmp_path)
    first = jobs.claim_job("one", now=100, lease_seconds=10)
    assert first["id"] == job["id"]
    assert jobs.claim_job("two", now=109, lease_seconds=10) is None
    second = jobs.claim_job("two", now=111, lease_seconds=10)
    assert second["id"] == job["id"]
    assert second["attempts"] == 2
    assert (
        jobs.enqueue_import(job["source_id"], [{"pages": []}], "direct", "test-key")[
            "id"
        ]
        == job["id"]
    )


def test_retry_after_acceptance_preserves_later_edits(tmp_path):
    store, jobs, job = setup_job(tmp_path)
    claimed = jobs.claim_job("worker")
    jobs.process_direct(claimed["id"], "worker")
    draft = jobs.get_job(job["id"])["drafts"][0]
    accepted = jobs.accept_draft(
        job["id"], draft["id"], draft["revision"], None, acknowledge=True
    )
    edited = store.save_arrangement(
        accepted.id, accepted.revision, "{title: Changed}\n[G]New"
    )
    again = jobs.accept_draft(
        job["id"], draft["id"], draft["revision"], None, acknowledge=True
    )
    assert again.id == edited.id
    assert again.revision == edited.revision
    assert again.source == edited.source


def test_draft_edits_require_current_revision(tmp_path):
    _, jobs, job = setup_job(tmp_path)
    claimed = jobs.claim_job("worker")
    jobs.process_direct(claimed["id"], "worker")
    draft = jobs.get_job(job["id"])["drafts"][0]
    updated = jobs.update_draft(job["id"], draft["id"], draft["revision"], "[F]Changed")
    with pytest.raises(ConflictError):
        jobs.update_draft(job["id"], draft["id"], draft["revision"], "[D]Stale")
    assert jobs.get_job(job["id"])["drafts"][0]["source"] == updated["source"]


def test_worker_cannot_complete_after_lease_is_reclaimed(tmp_path):
    _, jobs, job = setup_job(tmp_path)
    jobs.claim_job("old", now=100, lease_seconds=10)
    jobs.claim_job("new", now=111, lease_seconds=10)
    with pytest.raises(ConflictError):
        jobs.process_direct(job["id"], "old")
    with connect(jobs.store.database) as db:
        assert db.execute("SELECT count(*) FROM import_drafts").fetchone()[0] == 0


def test_acceptance_reserves_draft_against_concurrent_edits(tmp_path, monkeypatch):
    store, jobs, job = setup_job(tmp_path)
    jobs.process_direct(jobs.claim_job("worker")["id"], "worker")
    draft = jobs.get_job(job["id"])["drafts"][0]
    original_create = store.create_arrangement

    def race(*args, **kwargs):
        with pytest.raises(ConflictError):
            jobs.update_draft(
                job["id"], draft["id"], draft["revision"], "[D]Late change"
            )
        return original_create(*args, **kwargs)

    monkeypatch.setattr(store, "create_arrangement", race)
    accepted = jobs.accept_draft(
        job["id"], draft["id"], draft["revision"], None, acknowledge=True
    )
    assert accepted.source == draft["source"]


def test_book_selection_creates_multiple_arrangements_shared_source(tmp_path):
    from pypdf import PdfWriter

    store = LibraryStore(tmp_path)
    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    writer.write(pdf)
    pdf.seek(0)
    source = store.register_source(pdf, "book.pdf", "pdf")
    jobs = ImportJobs(store)
    job = jobs.enqueue_import(
        source.id, [{"pages": [1]}, {"pages": [1, 2]}], "local", "book"
    )
    jobs.process_local(jobs.claim_job("worker")["id"], "worker")
    drafts = jobs.get_job(job["id"])["drafts"]
    assert len(drafts) == 2
    drafts = [
        jobs.update_draft(job["id"], d["id"], d["revision"], "[C]Reviewed")
        for d in drafts
    ]
    first = jobs.accept_draft(
        job["id"], drafts[0]["id"], drafts[0]["revision"], None, acknowledge=True
    )
    assert jobs.get_job(job["id"])["state"] == "needs-review"
    second = jobs.accept_draft(
        job["id"], drafts[1]["id"], drafts[1]["revision"], None, acknowledge=True
    )
    assert first.id != second.id
    assert (
        first.source_refs[0]["source_id"]
        == second.source_refs[0]["source_id"]
        == source.id
    )
    assert second.source_refs[0]["pages"] == [1, 2]
    assert jobs.get_job(job["id"])["state"] == "accepted"


def test_worker_records_failures_and_heartbeat_without_source_text(tmp_path):
    from server.songbook.imports.worker import run_once

    store = LibraryStore(tmp_path)
    source = store.register_source(io.BytesIO(b"not a pdf"), "broken.pdf", "pdf")
    jobs = ImportJobs(store)
    job = jobs.enqueue_import(source.id, [{"pages": [1]}], "local", "broken")
    assert run_once(jobs, "worker")
    failed = jobs.get_job(job["id"])
    assert failed["state"] == "failed"
    assert failed["error_code"] == "conversion_failed"
    assert "not a pdf" not in str(failed)
    with connect(store.database) as db:
        assert (
            db.execute("SELECT worker_id FROM worker_heartbeat").fetchone()[0]
            == "worker"
        )


def test_required_worker_readiness_depends_on_recent_heartbeat(tmp_path):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.imports.worker import heartbeat
    from server.songbook.main import create_app

    app = create_app(Settings(library_root=tmp_path, worker_required=True))
    jobs = ImportJobs(app.state.store)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/health/ready").status_code == 503
        heartbeat(jobs, "worker")
        assert client.get("/health/ready").status_code == 200
        with connect(app.state.store.database) as db:
            db.execute("UPDATE worker_heartbeat SET last_seen=0")
        assert client.get("/health/ready").status_code == 503


def test_authenticated_import_api_preserves_draft_edits_and_accepts(tmp_path):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.imports.worker import run_once
    from server.songbook.main import create_app

    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/imports").status_code == 401
        response = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": response.json()["csrf"],
        }
        upload = client.post(
            "/api/imports/sources?filename=test.cho",
            content=b"{title: Test}\n[C]Hello",
            headers=headers,
        )
        assert upload.status_code == 201
        source_id = upload.json()["id"]
        queued = client.post(
            "/api/imports",
            json={
                "source_id": source_id,
                "selection": [{"pages": []}],
                "method": "direct",
                "idempotency_key": "request-1",
            },
            headers=headers,
        )
        assert queued.status_code == 201
        assert run_once(app.state.imports, "worker")
        job = client.get("/api/imports/" + queued.json()["id"]).json()
        draft = job["drafts"][0]
        edited = client.put(
            f"/api/imports/{job['id']}/drafts/{draft['id']}",
            json={"source": "[G]Revised", "revision": draft["revision"]},
            headers=headers,
        )
        assert edited.status_code == 200
        stale = client.put(
            f"/api/imports/{job['id']}/drafts/{draft['id']}",
            json={"source": "[D]Stale", "revision": draft["revision"]},
            headers=headers,
        )
        assert stale.status_code == 409
        accepted = client.post(
            f"/api/imports/{job['id']}/drafts/{draft['id']}/accept",
            json={"revision": edited.json()["revision"], "acknowledge": True},
            headers=headers,
        )
        assert accepted.status_code == 200
        assert accepted.json()["source"] == "[G]Revised"


def test_scan_ignores_sidecars_and_non_supported_files(tmp_path):
    from server.songbook.imports.service import scan_source_root

    root = tmp_path / "input"
    root.mkdir()
    (root / "one.cho").write_text("[C]One")
    (root / "book.pdf").write_bytes(b"pdf")
    (root / "._one.cho").write_text("sidecar")
    (root / "notes.txt").write_text("not music")
    outside = tmp_path / "outside.cho"
    outside.write_text("outside")
    (root / "escape.cho").symlink_to(outside)
    assert scan_source_root(root, ".") == ["book.pdf", "one.cho"]
    with pytest.raises(ValueError):
        scan_source_root(root, "../")


def test_scan_api_confines_paths_to_configured_root(tmp_path):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.main import create_app

    root = tmp_path / "read-only"
    root.mkdir()
    (root / "song.cho").write_text("[C]Song")
    app = create_app(
        Settings(
            library_root=tmp_path / "managed",
            allowed_origins=("http://testserver",),
            source_roots={"music": root},
        )
    )
    app.state.auth.set_password("synthetic test password")
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        response = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": response.json()["csrf"],
        }
        assert client.get("/api/imports/scan/music").json()["files"] == ["song.cho"]
        assert client.get("/api/imports/scan/music?path=..").status_code == 400
        registered = client.post(
            "/api/imports/scan/music", json={"path": "song.cho"}, headers=headers
        )
        assert registered.status_code == 201
        assert (root / "song.cho").read_text() == "[C]Song"
        assert (
            client.post(
                "/api/imports/scan/music", json={"path": "../song.cho"}, headers=headers
            ).status_code
            == 400
        )


def test_failed_jobs_require_explicit_retry_and_bound_attempts(tmp_path):
    from server.songbook.imports.worker import run_once

    store = LibraryStore(tmp_path)
    source = store.register_source(io.BytesIO(b"invalid"), "bad.pdf", "pdf")
    jobs = ImportJobs(store)
    job = jobs.enqueue_import(source.id, [{"pages": [1]}], "local", "bad-pdf")
    for attempt in range(1, 4):
        assert run_once(jobs, "worker")
        assert jobs.get_job(job["id"])["attempts"] == attempt
        assert jobs.get_job(job["id"])["state"] == "failed"
        if attempt < 3:
            jobs.retry_job(job["id"])
    with pytest.raises(ValueError):
        jobs.retry_job(job["id"])


def test_provider_status_never_returns_credentials(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.main import create_app

    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-provider-key")
    monkeypatch.setenv("SONGBOOK_ANTHROPIC_MODEL", "test-model")
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/provider").status_code == 401
        client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        response = client.get("/api/provider")
        assert response.status_code == 200
        assert "private-provider-key" not in response.text
        assert response.json()["model"] == "test-model"


def test_import_selection_is_bounded_before_queueing(tmp_path):
    store = LibraryStore(tmp_path)
    source = store.register_source(io.BytesIO(b"pdf"), "book.pdf", "pdf")
    jobs = ImportJobs(store)
    with pytest.raises(ValueError):
        jobs.enqueue_import(
            source.id,
            [{"pages": list(range(1, 21))}, {"pages": [21]}],
            "local",
            "too-many",
        )
    with connect(store.database) as db:
        assert db.execute("SELECT count(*) FROM import_jobs").fetchone()[0] == 0


def test_acceptance_requires_acknowledging_parser_warnings(tmp_path):
    _, jobs, job = setup_job(tmp_path)
    jobs.process_direct(jobs.claim_job("worker")["id"], "worker")
    draft = jobs.get_job(job["id"])["drafts"][0]
    updated = jobs.update_draft(
        job["id"], draft["id"], draft["revision"], "{future: keep}\n[C]Hello"
    )
    with pytest.raises(ValueError, match="acknowledgement"):
        jobs.accept_draft(job["id"], draft["id"], updated["revision"], None)
    assert (
        jobs.accept_draft(
            job["id"], draft["id"], updated["revision"], None, acknowledge=True
        ).source
        == updated["source"]
    )


def test_verified_chordpro_precedes_pdf_draft(tmp_path):
    store = LibraryStore(tmp_path)
    chordpro = store.register_source(
        io.BytesIO(b"{title: Original}\n[C]Verified"), "song.cho", "cho"
    )
    pdf = store.register_source(io.BytesIO(b"original book"), "book.pdf", "pdf")
    jobs = ImportJobs(store)
    selection = [{"pages": [], "paired_source_id": pdf.id, "paired_pages": [2, 3]}]
    job = jobs.enqueue_import(chordpro.id, selection, "direct", "paired")
    jobs.process_direct(jobs.claim_job("worker")["id"], "worker")
    draft = jobs.get_job(job["id"])["drafts"][0]
    accepted = jobs.accept_draft(
        job["id"], draft["id"], draft["revision"], None, acknowledge=True
    )
    assert accepted.source == "{title: Original}\n[C]Verified"
    assert {ref["source_id"] for ref in accepted.source_refs} == {chordpro.id, pdf.id}
    assert next(
        ref["pages"] for ref in accepted.source_refs if ref["source_id"] == pdf.id
    ) == [2, 3]


def test_import_selection_rejects_invalid_methods_before_queueing(tmp_path):
    store = LibraryStore(tmp_path)
    source = store.register_source(io.BytesIO(b"data"), "book.pdf", "pdf")
    jobs = ImportJobs(store)
    with pytest.raises(ValueError):
        jobs.enqueue_import(source.id, [{"pages": []}], "local", "empty-pages")
    with pytest.raises(ValueError):
        jobs.enqueue_import(source.id, [{"pages": [0]}], "local", "bad-page")
    with pytest.raises(ValueError):
        jobs.enqueue_import(
            source.id,
            [{"pages": [1], "rectangles": {"1": [0.8, 0, 0.2, 1]}}],
            "local",
            "bad-crop",
        )


def test_ai_requires_explicit_authorization_before_queueing(tmp_path):
    store = LibraryStore(tmp_path)
    source = store.register_source(io.BytesIO(b"pdf"), "book.pdf", "pdf")
    jobs = ImportJobs(store)
    with pytest.raises(ValueError, match="authorization"):
        jobs.enqueue_import(source.id, [{"pages": [1]}], "ai", "unapproved")


def test_ai_conversion_uses_only_authorized_selected_pages_and_requires_review(
    tmp_path,
):
    from pypdf import PdfWriter

    from server.songbook.imports.providers.base import ProviderStatus, VisionDraft

    class FakeProvider:
        def __init__(self):
            self.calls = []

        def status(self):
            return ProviderStatus(True, "fake", "test-model")

        def convert(self, request):
            self.calls.append([page.page for page in request.pages])
            return VisionDraft(
                "[C]Synthetic", ["Uncertain chord"], "test-model", {}, "synthetic"
            )

    store = LibraryStore(tmp_path)
    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    writer.write(pdf)
    pdf.seek(0)
    source = store.register_source(pdf, "synthetic.pdf", "pdf")
    jobs = ImportJobs(store)
    selection = [
        {"pages": [2], "provider": "fake", "model": "test-model", "authorization": True}
    ]
    job = jobs.enqueue_import(source.id, selection, "ai", "ai-approved")
    jobs.claim_job("worker")
    provider = FakeProvider()
    jobs.process_ai(job["id"], "worker", provider)
    assert provider.calls == [[2]]
    draft = jobs.get_job(job["id"])["drafts"][0]
    assert draft["source"] == "[C]Synthetic"
    assert draft["provider_metadata"]["model"] == "test-model"
    assert draft["provenance"][0]["page"] == 2
    assert draft["diagnostics"]
    with pytest.raises(ValueError, match="acknowledgement"):
        jobs.accept_draft(job["id"], draft["id"], draft["revision"], None)


def test_worker_restart_recovers_expired_local_job(tmp_path):
    import os
    import subprocess
    import sys
    import time

    _, jobs, job = setup_job(tmp_path)
    jobs.claim_job("dead-worker", now=1, lease_seconds=1)
    env = os.environ.copy()
    env["SONGBOOK_LIBRARY_ROOT"] = str(tmp_path)
    env["SONGBOOK_ALLOW_EXTERNAL_AI"] = "false"
    process = subprocess.Popen(
        [sys.executable, "-m", "server.songbook.cli", "worker"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while (
            time.monotonic() < deadline
            and jobs.get_job(job["id"])["state"] != "needs-review"
        ):
            assert process.poll() is None
            time.sleep(0.05)
        resumed = jobs.get_job(job["id"])
        assert resumed["state"] == "needs-review"
        assert resumed["attempts"] == 2
        assert len(resumed["drafts"]) == 1
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_similar_title_suggestions_never_merge_automatically(tmp_path):
    store, jobs, job = setup_job(tmp_path)
    existing = store.create_arrangement(
        None, "{title: Synthetic}\n[G]Existing", [], None
    )
    jobs.process_direct(jobs.claim_job("worker")["id"], "worker")
    draft = jobs.get_job(job["id"])["drafts"][0]
    suggestions = jobs.suggest_duplicates(job["id"], draft["id"])
    assert any(suggestion["id"] == existing.id for suggestion in suggestions)
    accepted = jobs.accept_draft(
        job["id"], draft["id"], draft["revision"], None, acknowledge=True
    )
    assert accepted.id != existing.id
    assert store.get_arrangement(existing.id).source.endswith("[G]Existing")


def test_lease_renewal_respects_worker_ownership(tmp_path):
    _, jobs, job = setup_job(tmp_path)
    jobs.claim_job("first", now=100, lease_seconds=10)
    assert jobs.renew_lease(job["id"], "first", now=105, lease_seconds=10)
    assert jobs.claim_job("second", now=111, lease_seconds=10) is None
    assert jobs.claim_job("second", now=116, lease_seconds=10)
    assert not jobs.renew_lease(job["id"], "first", now=117, lease_seconds=10)
