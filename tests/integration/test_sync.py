"""Reconnection status checks never mutate cached or canonical content."""

from fastapi.testclient import TestClient

from server.songbook.config import Settings
from server.songbook.main import create_app


def test_sync_distinguishes_changed_deleted_and_unknown(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    current = app.state.store.create_arrangement(
        None, "{title: Current}\n[C]Line", [], None
    )
    changed = app.state.store.create_arrangement(
        None, "{title: Changed}\n[C]Before", [], None
    )
    deleted = app.state.store.create_arrangement(
        None, "{title: Deleted}\n[C]Line", [], None
    )
    app.state.store.save_arrangement(
        changed.id, changed.revision, "{title: Changed}\n[C]After"
    )
    metadata = app.state.library.metadata(deleted.id)
    app.state.library.delete(deleted.id, metadata["revision"])
    playlist = app.state.setlists.create("Set")
    body = {
        "arrangements": [
            {"id": current.id, "revision": current.revision},
            {"id": changed.id, "revision": changed.revision},
            {"id": deleted.id, "revision": deleted.revision},
            {"id": "missing", "revision": "x"},
        ],
        "setlists": [{"id": playlist["id"], "revision": playlist["revision"]}],
    }
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.post("/api/sync/check", json=body).status_code == 401
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        response = client.post(
            "/api/sync/check",
            json=body,
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": auth.json()["csrf"],
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert [row["state"] for row in result["arrangements"]] == [
            "current",
            "outdated",
            "deleted",
            "unavailable",
        ]
        assert result["setlists"][0]["state"] == "current"
        assert app.state.store.get_arrangement(changed.id).source.endswith("[C]After")


def test_deleted_setlist_is_distinct_from_unknown(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    playlist = app.state.setlists.create("Removed")
    app.state.setlists.delete(playlist["id"], playlist["revision"])
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        response = client.post(
            "/api/sync/check",
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": auth.json()["csrf"],
            },
            json={
                "setlists": [
                    {"id": playlist["id"], "revision": playlist["revision"]},
                    {"id": "unknown", "revision": "x"},
                ]
            },
        )
        assert response.status_code == 200
        assert [entry["state"] for entry in response.json()["setlists"]] == [
            "deleted",
            "unavailable",
        ]


def test_sync_is_bounded_and_requires_csrf(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        assert (
            client.post(
                "/api/sync/check", json={}, headers={"Origin": "http://testserver"}
            ).status_code
            == 403
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        response = client.post(
            "/api/sync/check",
            json={
                "arrangements": [{"id": str(i), "revision": "x"} for i in range(501)]
            },
            headers=headers,
        )
        assert response.status_code == 422
