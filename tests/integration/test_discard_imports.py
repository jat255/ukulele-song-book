import io

import pytest

from server.songbook.imports.jobs import ImportJobs
from server.songbook.storage.arrangements import ConflictError, LibraryStore
from server.songbook.storage.db import connect


def pending(tmp_path):
    store = LibraryStore(tmp_path)
    jobs = ImportJobs(store)
    source = store.register_source(
        io.BytesIO(b"{title: Synthetic}\n[C]Line"), "synthetic.cho", "cho"
    )
    job = jobs.enqueue_import(source.id, [{"pages": []}], "direct", "first")
    jobs.claim_job("worker")
    jobs.process_direct(job["id"], "worker")
    return store, jobs, jobs.get_job(job["id"])


def versions(job):
    return {
        draft["id"]: draft["revision"]
        for draft in job["drafts"]
        if not draft["accepted_id"]
    }


def test_discard_preserves_source_and_allows_a_fresh_attempt(tmp_path):
    store, jobs, job = pending(tmp_path)
    jobs.discard_job(job["id"], job["state"], versions(job))
    with pytest.raises(KeyError):
        jobs.get_job(job["id"])
    with pytest.raises(KeyError):
        jobs.process_direct(job["id"], "late-worker")
    with connect(store.database) as db:
        assert db.execute(
            "SELECT 1 FROM sources WHERE id=?", (job["source_id"],)
        ).fetchone()
    fresh = jobs.enqueue_import(job["source_id"], [{"pages": []}], "direct", "second")
    assert fresh["id"] != job["id"] and fresh["state"] == "queued"


def test_discard_rejects_changed_drafts_and_active_workers(tmp_path):
    _, jobs, job = pending(tmp_path)
    draft = job["drafts"][0]
    jobs.update_draft(
        job["id"], draft["id"], draft["revision"], "{title: Changed}\n[G]Line"
    )
    with pytest.raises(ConflictError):
        jobs.discard_job(job["id"], job["state"], versions(job))
    with connect(jobs.store.database) as db:
        db.execute(
            "UPDATE import_jobs SET state='processing',worker_id='worker' WHERE id=?",
            (job["id"],),
        )
    with pytest.raises(ConflictError):
        jobs.discard_job(job["id"], "processing", versions(jobs.get_job(job["id"])))


def test_partial_acceptance_keeps_song_and_accepted_provenance(tmp_path):
    store, jobs, job = pending(tmp_path)
    draft = job["drafts"][0]
    song = jobs.accept_draft(job["id"], draft["id"], draft["revision"], None)
    with connect(store.database) as db:
        db.execute(
            "INSERT INTO import_drafts VALUES ('pending-extra',?,1,?,'extra','[]','[]',NULL,NULL,NULL)",
            (job["id"], "{title: Extra}"),
        )
        db.execute(
            "UPDATE import_jobs SET state='needs-review' WHERE id=?", (job["id"],)
        )
        for ident in [draft["id"], "pending-extra"]:
            db.execute(
                "INSERT INTO import_draft_provenance VALUES (?, '{}', '[]', '[]')",
                (ident,),
            )
    current = jobs.get_job(job["id"])
    jobs.discard_job(job["id"], current["state"], versions(current))
    assert store.get_arrangement(song.id).source == song.source
    kept = jobs.get_job(job["id"])
    assert kept["state"] == "accepted" and len(kept["drafts"]) == 1
    with connect(store.database) as db:
        assert [
            row[0] for row in db.execute("SELECT draft_id FROM import_draft_provenance")
        ] == [draft["id"]]
    with pytest.raises(ConflictError):
        jobs.discard_job(job["id"], "accepted", {})


def test_acceptance_in_progress_cannot_be_discarded(tmp_path):
    store, jobs, job = pending(tmp_path)
    with connect(store.database) as db:
        db.execute(
            "UPDATE import_drafts SET accepting_revision=revision WHERE job_id=?",
            (job["id"],),
        )
    with pytest.raises(ConflictError):
        jobs.discard_job(job["id"], job["state"], versions(job))


def test_discard_api_requires_auth_and_csrf(tmp_path):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.main import create_app

    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    source = app.state.store.register_source(
        io.BytesIO(b"{title: API}\n[C]Synthetic"), "api.cho", "cho"
    )
    job = app.state.imports.enqueue_import(
        source.id, [{"pages": []}], "direct", "api-discard"
    )
    body = {"state": "queued", "drafts": {}}
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert (
            client.request("DELETE", f"/api/imports/{job['id']}", json=body).status_code
            == 401
        )
        session = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        ).json()
        assert (
            client.request("DELETE", f"/api/imports/{job['id']}", json=body).status_code
            == 403
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": session["csrf"]}
        assert (
            client.request(
                "DELETE", f"/api/imports/{job['id']}", json=body, headers=headers
            ).status_code
            == 204
        )
        assert client.get(f"/api/imports/{job['id']}").status_code == 404
        assert client.get(f"/api/sources/{source.id}/original").status_code == 200
