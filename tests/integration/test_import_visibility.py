import io

from fastapi.testclient import TestClient

from server.songbook.config import Settings
from server.songbook.main import create_app


def test_hide_and_restore_import_persists_without_affecting_draft_or_source(tmp_path):
    settings = Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    app = create_app(settings)
    source = app.state.store.register_source(
        io.BytesIO(b"{title: Test}\n[C]Hello"), "test.cho", "cho"
    )
    job = app.state.imports.enqueue_import(
        source.id, [{"pages": []}], "direct", "visible-test"
    )
    app.state.imports.claim_job("worker")
    app.state.imports.process_direct(job["id"], "worker")
    path = f"/api/imports/{job['id']}/visibility"
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        csrf = client.get("/api/session").json()["csrf"]
        headers = {"Origin": "http://testserver", "X-CSRF-Token": csrf}
        assert client.put(path, json={"hidden": True}).status_code == 403
        assert (
            client.put(path, json={"hidden": True}, headers=headers).status_code == 200
        )
        data = client.get("/api/imports").json()[0]
        assert data["hidden"] is True
        assert data["drafts"][0]["source"] == "{title: Test}\n[C]Hello"
    restarted = create_app(settings)
    assert restarted.state.imports.get_job(job["id"])["hidden"] is True
    with TestClient(restarted, client=("127.0.0.1", 1234)) as client:
        csrf = client.get("/api/session").json()["csrf"]
        headers = {"Origin": "http://testserver", "X-CSRF-Token": csrf}
        assert (
            client.put(path, json={"hidden": False}, headers=headers).status_code == 200
        )
        assert client.get("/api/imports").json()[0]["hidden"] is False
        assert (
            client.put(
                "/api/imports/missing/visibility",
                json={"hidden": True},
                headers=headers,
            ).status_code
            == 404
        )
        assert client.get(f"/api/sources/{source.id}/original").status_code == 200


def test_hiding_accepted_import_keeps_song_and_queue_history(tmp_path):
    app = create_app(Settings(library_root=tmp_path))
    source = app.state.store.register_source(
        io.BytesIO(b"{title: Song}\n[C]Hello"), "song.cho", "cho"
    )
    job = app.state.imports.enqueue_import(
        source.id, [{"pages": []}], "direct", "accepted-test"
    )
    app.state.imports.claim_job("worker")
    app.state.imports.process_direct(job["id"], "worker")
    draft = app.state.imports.get_job(job["id"])["drafts"][0]
    song = app.state.imports.accept_draft(
        job["id"], draft["id"], draft["revision"], None
    )
    app.state.imports.set_hidden(job["id"], True)
    assert app.state.store.get_arrangement(song.id).source == draft["source"]
    assert app.state.imports.get_job(job["id"])["drafts"][0]["accepted_id"] == song.id
    app.state.imports.set_hidden(job["id"], False)
    assert app.state.imports.get_job(job["id"])["hidden"] is False
