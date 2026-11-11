import io

from fastapi.testclient import TestClient

from server.songbook.config import Settings
from server.songbook.main import create_app


def setup_app(tmp_path):
    settings = Settings(
        library_root=tmp_path,
        allowed_origins=("http://testserver",),
        loopback_http=True,
        session_seconds=60,
    )
    app = create_app(settings)
    app.state.auth.set_password("correct horse battery staple")
    source = app.state.store.register_source(
        io.BytesIO(b"%PDF-1.4\n"), "original.pdf", "pdf"
    )
    item = app.state.store.create_arrangement(
        None, "{title: Test}\n[C]Hello", [{"source_id": source.id, "pages": [1]}], None
    )
    return app, source, item


def login(client):
    response = client.post(
        "/api/session",
        json={"password": "correct horse battery staple"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200
    return response.json()["csrf"]


def test_library_requires_session_and_logout_revokes(tmp_path):
    app, source, item = setup_app(tmp_path)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        for path in (
            f"/api/arrangements/{item.id}",
            f"/api/sources/{source.id}/original",
            f"/api/sources/{source.id}/pages/1.png",
        ):
            assert client.get(path).status_code == 401
        csrf = login(client)
        assert (
            client.get(f"/api/arrangements/{item.id}").json()["source"] == item.source
        )
        assert client.get(f"/api/sources/{source.id}/original").content == b"%PDF-1.4\n"
        assert (
            client.delete(
                "/api/session",
                headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
            ).status_code
            == 204
        )
        assert client.get(f"/api/arrangements/{item.id}").status_code == 401


def test_mutations_require_origin_and_csrf(tmp_path):
    app, _, item = setup_app(tmp_path)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        csrf = login(client)
        path = f"/api/arrangements/{item.id}"
        assert (
            client.put(
                path, json={"source": "[G]New"}, headers={"If-Match": item.revision}
            ).status_code
            == 403
        )
        assert (
            client.put(
                path,
                json={"source": "[G]New"},
                headers={
                    "Origin": "https://evil.example",
                    "X-CSRF-Token": csrf,
                    "If-Match": item.revision,
                },
            ).status_code
            == 403
        )
        response = client.put(
            path,
            json={"source": "[G]New"},
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": csrf,
                "If-Match": item.revision,
            },
        )
        assert response.status_code == 200
        stale = client.put(
            path,
            json={"source": "[D]Other"},
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": csrf,
                "If-Match": item.revision,
            },
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "revision_conflict"


def test_password_rate_limit_and_expiry(tmp_path):
    app, _, item = setup_app(tmp_path)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        for _ in range(5):
            assert (
                client.post(
                    "/api/session",
                    json={"password": "wrong"},
                    headers={"Origin": "http://testserver"},
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/api/session",
                json={"password": "wrong"},
                headers={"Origin": "http://testserver"},
            ).status_code
            == 429
        )
    app.state.auth.clear_failures()
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        login(client)
        app.state.auth.expire_all()
        assert client.get(f"/api/arrangements/{item.id}").status_code == 401


def test_forged_source_ids_and_health_are_safe(tmp_path):
    app, _, _ = setup_app(tmp_path)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        login(client)
        assert client.get("/api/sources/not-a-uuid/original").status_code == 404
        assert client.get("/api/sources/%2e%2e/original").status_code in (404, 405)


def test_loopback_http_rejects_remote_clients(tmp_path):
    app, _, _ = setup_app(tmp_path)
    with TestClient(app, client=("203.0.113.5", 1234)) as client:
        assert client.get("/health/live").status_code == 403
        assert (
            client.post(
                "/api/session",
                json={"password": "correct horse battery staple"},
                headers={"Origin": "http://testserver"},
            ).status_code
            == 403
        )


def test_secure_mode_rejects_plain_http(tmp_path):
    app = create_app(
        Settings(
            library_root=tmp_path,
            allowed_origins=("https://testserver",),
            loopback_http=False,
        )
    )
    app.state.auth.set_password("correct horse battery staple")
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert (
            client.post(
                "/api/session",
                json={"password": "correct horse battery staple"},
                headers={"Origin": "https://testserver"},
            ).status_code
            == 403
        )


def test_concurrent_bad_passwords_cannot_bypass_rate_limit(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import HTTPException

    app, _, _ = setup_app(tmp_path)

    def attempt(_):
        try:
            app.state.auth.authenticate("wrong", "same-client")
        except HTTPException as exc:
            return exc.status_code
        return 200

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert results.count(401) == 5
    assert results.count(429) == 3


def test_failure_storage_is_bounded(tmp_path):
    import time

    from server.songbook.storage.db import connect

    app, _, _ = setup_app(tmp_path)
    with connect(app.state.store.database) as db:
        db.executemany(
            "INSERT INTO login_failures VALUES (?,?)",
            [(f"client-{i}", time.time()) for i in range(2000)],
        )
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        app.state.auth.authenticate("wrong", "new-client")
    assert error.value.status_code == 429
    with connect(app.state.store.database) as db:
        assert db.execute("SELECT count(*) FROM login_failures").fetchone()[0] <= 2000


def test_source_symlink_escape_is_not_served(tmp_path):
    from server.songbook.storage.db import connect

    app, source, _ = setup_app(tmp_path)
    outside = tmp_path.parent / "private-file"
    outside.write_bytes(b"not allowed")
    path = app.state.store.root / "sources" / source.id / "escape.pdf"
    path.symlink_to(outside)
    with connect(app.state.store.database) as db:
        db.execute(
            "UPDATE sources SET path=? WHERE id=?",
            (str(path.relative_to(app.state.store.root)), source.id),
        )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        login(client)
        response = client.get(f"/api/sources/{source.id}/original")
        assert response.status_code == 404
        assert b"not allowed" not in response.content


def test_cookie_is_httponly_and_secure_in_https_mode(tmp_path):
    app = create_app(
        Settings(
            library_root=tmp_path,
            allowed_origins=("https://testserver",),
            loopback_http=False,
        )
    )
    app.state.auth.set_password("correct horse battery staple")
    with TestClient(
        app, base_url="https://testserver", client=("127.0.0.1", 1234)
    ) as client:
        response = client.post(
            "/api/session",
            json={"password": "correct horse battery staple"},
            headers={"Origin": "https://testserver"},
        )
        cookie = response.headers["set-cookie"].lower()
        assert (
            "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
        )


def test_built_shell_is_served_without_library_data(tmp_path):
    app, _, item = setup_app(tmp_path)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert item.source not in response.text


def test_corrupt_pdf_remains_downloadable_and_reports_error(tmp_path):
    app, source, _ = setup_app(tmp_path)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        login(client)
        response = client.get(f"/api/sources/{source.id}/original")
        assert response.content == b"%PDF-1.4\n"
        assert response.headers["content-disposition"] == "attachment"
        assert response.headers["x-songbook-source-error"] == "invalid_pdf"
        assert client.get(f"/api/sources/{source.id}/pages/1.png").status_code == 400


def test_readiness_reports_missing_database(tmp_path):
    app, _, _ = setup_app(tmp_path)
    app.state.store.database.unlink()
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503


def test_pdf_page_is_a_bounded_managed_derivative(tmp_path):
    from pypdf import PdfWriter

    app, _, _ = setup_app(tmp_path)
    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(pdf)
    pdf.seek(0)
    source = app.state.store.register_source(pdf, "valid.pdf", "pdf")
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        login(client)
        original = client.get(f"/api/sources/{source.id}/original")
        assert original.headers["content-type"] == "application/pdf"
        assert original.headers["content-disposition"] == "inline"
        image = client.get(f"/api/sources/{source.id}/pages/1.png")
        assert image.status_code == 200
        assert image.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert list((tmp_path / "derivatives" / source.id).glob("*.png"))
        assert client.get(f"/api/sources/{source.id}/pages/2.png").status_code == 400


def test_app_routes_serve_shell_but_unknown_api_is_not_html(tmp_path):
    app, _, _ = setup_app(tmp_path)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        for route in ("/imports", "/player", "/print", "/login"):
            response = client.get(route)
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
        assert client.get("/api/not-a-route").status_code == 404


def test_failed_login_does_not_echo_secrets_or_log_song_text(tmp_path, caplog):
    app, _, item = setup_app(tmp_path)
    secret = "incorrect unique password"
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        response = client.post(
            "/api/session",
            json={"password": secret},
            headers={"Origin": "http://testserver"},
        )
    assert secret not in response.text
    assert secret not in caplog.text
    assert item.source not in response.text
    assert item.source not in caplog.text


def test_unsupported_original_type_is_rejected(tmp_path):
    import pytest

    app, _, _ = setup_app(tmp_path)
    with pytest.raises(ValueError, match="Unsupported"):
        app.state.store.register_source(io.BytesIO(b"<script>"), "song.html", "html")
