from fastapi.testclient import TestClient

from server.songbook.config import Settings
from server.songbook.main import create_app


def test_local_session_opens_without_password_and_allows_edits(tmp_path):
    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    item = app.state.store.create_arrangement(None, "{title: Test}\n[C]Hello", [], None)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        session = client.get("/api/session")
        assert session.status_code == 200
        csrf = session.json()["csrf"]
        assert client.get(f"/api/arrangements/{item.id}").status_code == 200
        response = client.put(
            f"/api/arrangements/{item.id}",
            json={"source": "[G]New"},
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": csrf,
                "If-Match": item.revision,
            },
        )
        assert response.status_code == 200
