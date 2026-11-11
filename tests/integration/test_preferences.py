"""Bounded, revision-checked preferences independent of music source."""

from fastapi.testclient import TestClient

from server.songbook.config import Settings
from server.songbook.main import create_app


def test_preferences_are_grouped_validated_and_revision_checked(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    song = app.state.store.create_arrangement(None, "{title: Test}\n[C]Hello", [], None)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get(f"/api/preferences/{song.id}").status_code == 401
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        initial = client.get(f"/api/preferences/{song.id}")
        assert initial.status_code == 200
        state = initial.json()
        assert state["schema_version"] == 1
        assert state["groups"]["play"]["value"]["fontPx"] == 20
        state["groups"]["play"]["value"]["fontPx"] = 28
        state["groups"]["play"]["updated_at"] = 100
        saved = client.put(
            f"/api/preferences/{song.id}",
            json=state,
            headers={**headers, "If-Match": initial.headers["etag"]},
        )
        assert saved.status_code == 200
        stale = client.put(
            f"/api/preferences/{song.id}",
            json=state,
            headers={**headers, "If-Match": initial.headers["etag"]},
        )
        assert stale.status_code == 409
        invalid = saved.json()
        invalid["groups"]["play"]["value"]["fontPx"] = 1000
        assert (
            client.put(
                f"/api/preferences/{song.id}",
                json=invalid,
                headers={**headers, "If-Match": saved.headers["etag"]},
            ).status_code
            == 422
        )
        assert app.state.store.get_arrangement(song.id).revision == song.revision


def test_readiness_detects_incomplete_migrations(tmp_path):
    from server.songbook.storage.db import connect

    app = create_app(Settings(library_root=tmp_path))
    with connect(app.state.store.database) as db:
        db.execute("DELETE FROM schema_migrations WHERE version=5")
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/health/ready").status_code == 503


def test_app_defaults_apply_to_new_arrangements(tmp_path):
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
        initial = client.get("/api/preferences/defaults")
        assert initial.status_code == 200
        data = initial.json()
        data["groups"]["play"]["value"]["fontPx"] = 24
        response = client.put(
            "/api/preferences/defaults",
            json=data,
            headers={**headers, "If-Match": initial.headers["etag"]},
        )
        assert response.status_code == 200
        assert (
            client.get(f"/api/preferences/{song.id}").json()["groups"]["play"]["value"][
                "fontPx"
            ]
            == 24
        )
