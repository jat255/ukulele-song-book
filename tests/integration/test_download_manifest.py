"""Authenticated manifests contain immutable, deduplicated download inputs."""

import io
import uuid

from fastapi.testclient import TestClient

from server.songbook.config import Settings
from server.songbook.main import create_app


def test_set_manifest_is_authenticated_and_deduplicates_repeated_songs(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    source = app.state.store.register_source(
        io.BytesIO(b"%PDF-1.4\n"), "original.pdf", "pdf"
    )
    song = app.state.store.create_arrangement(
        None, "{title: Test}\n[C]Line", [{"source_id": source.id, "pages": [1]}], None
    )
    playlist = app.state.setlists.create("Set")
    playlist = app.state.setlists.save_setlist(
        playlist["id"],
        playlist["revision"],
        "Set",
        [{"id": str(uuid.uuid4()), "arrangementId": song.id} for _ in range(2)],
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        path = f"/api/downloads/setlists/{playlist['id']}"
        assert client.get(path).status_code == 401
        client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        response = client.get(path)
        assert response.status_code == 200
        manifest = response.json()
        assert manifest["schemaVersion"] == 1
        assert manifest["libraryId"]
        assert len(manifest["snapshots"]) == 1
        assert manifest["snapshots"][0]["revision"] == song.revision
        assert manifest["snapshots"][0]["sha256"] == song.revision
        assert manifest["snapshots"][0]["size"] == len(song.source.encode())
        assert manifest["snapshots"][0]["mime"] == "text/plain; charset=utf-8"
        assert [item["id"] for item in manifest["setlist"]["items"]] == [
            item["id"] for item in playlist["items"]
        ]
        assert (
            len(manifest["assets"]) == 1 and manifest["assets"][0]["optional"] is True
        )


def test_missing_optional_original_does_not_block_song_manifest(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    source = app.state.store.register_source(
        io.BytesIO(b"%PDF-1.4\n"), "original.pdf", "pdf"
    )
    song = app.state.store.create_arrangement(
        None, "[C]Line", [{"source_id": source.id, "pages": [1]}], None
    )
    (tmp_path / source.path).unlink()
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        response = client.get(f"/api/downloads/arrangements/{song.id}")
        assert response.status_code == 200
        assert response.json()["assets"][0]["available"] is False
        assert response.json()["assets"][0]["optional"] is True


def test_manifest_set_membership_and_snapshots_share_revision(tmp_path, monkeypatch):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    one = app.state.store.create_arrangement(None, "{title: One}\n[C]One", [], None)
    two = app.state.store.create_arrangement(None, "{title: Two}\n[C]Two", [], None)
    playlist = app.state.setlists.create("Set")
    first = {"id": str(uuid.uuid4()), "arrangementId": one.id}
    second = {"id": str(uuid.uuid4()), "arrangementId": two.id}
    playlist = app.state.setlists.save_setlist(
        playlist["id"], playlist["revision"], "Set", [first]
    )
    original = app.state.setlists.get
    changed = False

    def get_then_change(ident):
        nonlocal changed
        result = original(ident)
        if not changed:
            changed = True
            app.state.setlists.save_setlist(ident, result["revision"], "Set", [second])
        return result

    monkeypatch.setattr(app.state.setlists, "get", get_then_change)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        result = client.get(f"/api/downloads/setlists/{playlist['id']}")
        assert result.status_code == 200
        manifest = result.json()
        assert manifest["setlist"]["revision"] == original(playlist["id"])["revision"]
        assert [s["id"] for s in manifest["snapshots"]] == [two.id]


def test_manifest_refuses_missing_required_crop_asset(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    source = app.state.store.register_source(
        io.BytesIO(b"%PDF-1.4\n"), "original.pdf", "pdf"
    )
    song = app.state.store.create_arrangement(
        None,
        "[C]Line",
        [{"source_id": source.id, "pages": [1], "crop_asset_id": str(uuid.uuid4())}],
        None,
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        response = client.get(f"/api/downloads/arrangements/{song.id}")
        assert response.status_code == 409
        assert "crop" in response.json()["message"].lower()
