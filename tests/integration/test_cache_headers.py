from fastapi.testclient import TestClient

from server.songbook.config import Settings
from server.songbook.main import create_app

SHELL = "no-cache"
IMMUTABLE = "public, max-age=31536000, immutable"


def setup_app(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Songbook</title>")
    (dist / "sw.js").write_text("self.addEventListener('fetch',()=>{});")
    (dist / "manifest.webmanifest").write_text("{}")
    (dist / "assets" / "index-abc123.js").write_text("console.log('app');")
    settings = Settings(
        library_root=tmp_path / "library",
        allowed_origins=("http://testserver",),
        loopback_http=True,
        session_seconds=60,
    )
    return create_app(settings, web_dist=dist)


def test_shell_files_revalidate_on_every_load(tmp_path):
    with TestClient(setup_app(tmp_path), client=("127.0.0.1", 1234)) as client:
        for path in (
            "/",
            "/index.html",
            "/setlists",
            "/sw.js",
            "/manifest.webmanifest",
        ):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.headers["cache-control"] == SHELL, path


def test_hashed_assets_are_immutable(tmp_path):
    with TestClient(setup_app(tmp_path), client=("127.0.0.1", 1234)) as client:
        response = client.get("/assets/index-abc123.js")
        assert response.status_code == 200
        assert response.headers["cache-control"] == IMMUTABLE


def test_api_responses_are_never_stored(tmp_path):
    with TestClient(setup_app(tmp_path), client=("127.0.0.1", 1234)) as client:
        for path in ("/api/session", "/api/does-not-exist", "/health/live"):
            assert client.get(path).headers["cache-control"] == "no-store", path


def test_missing_asset_is_not_marked_immutable(tmp_path):
    with TestClient(setup_app(tmp_path), client=("127.0.0.1", 1234)) as client:
        response = client.get("/assets/index-old.js")
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"
