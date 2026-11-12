"""Owner-managed provider settings never disclose keys or contact providers on save."""

import stat

import pytest
from fastapi.testclient import TestClient

from server.songbook.config import Settings
from server.songbook.main import create_app


@pytest.fixture
def owner(tmp_path):
    app = create_app(
        Settings(
            library_root=tmp_path / "library", allowed_origins=("http://testserver",)
        )
    )
    app.state.auth.set_password("synthetic test password")
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/provider/settings").status_code == 401
        session = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        ).json()
        yield (
            client,
            {"Origin": "http://testserver", "X-CSRF-Token": session["csrf"]},
            app.state.store.root,
        )


def configuration(revision):
    return {
        "revision": revision,
        "name": "Synthetic NVIDIA",
        "protocol": "openai-compatible",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "synthetic-vision",
        "enabled": True,
        "api_key": "synthetic-provider-secret",
    }


def test_save_mask_retain_remove_and_revision_conflicts(owner):
    client, headers, root = owner
    original = client.get("/api/provider/settings").json()
    body = configuration(original["revision"])
    assert client.put("/api/provider/settings", json=body).status_code == 403
    response = client.put("/api/provider/settings", json=body, headers=headers)
    assert response.status_code == 200
    assert "synthetic-provider-secret" not in response.text
    saved = response.json()
    assert saved["has_api_key"] and saved["enabled"]
    path = root / ".ai-provider.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert (
        client.put("/api/provider/settings", json=body, headers=headers).status_code
        == 409
    )
    body.update(revision=saved["revision"], api_key=None, model="another-model")
    retained = client.put("/api/provider/settings", json=body, headers=headers).json()
    assert retained["has_api_key"]
    status = client.get("/api/provider").json()
    assert status["available"] and status["model"] == "another-model"
    assert status["provider"] != client.get("/api/provider/settings").json()["protocol"]
    body.update(revision=retained["revision"], api_key="", enabled=False)
    removed = client.put("/api/provider/settings", json=body, headers=headers).json()
    assert (
        not removed["has_api_key"]
        and not client.get("/api/provider").json()["available"]
    )


def test_endpoint_change_drops_old_key_and_invalid_urls_are_rejected(owner):
    client, headers, _ = owner
    body = configuration(client.get("/api/provider/settings").json()["revision"])
    saved = client.put("/api/provider/settings", json=body, headers=headers).json()
    body.update(
        revision=saved["revision"], base_url="https://other.example/v1", api_key=None
    )
    changed = client.put("/api/provider/settings", json=body, headers=headers).json()
    assert not changed["has_api_key"]
    for url in [
        "http://remote.example/v1",
        "https://user:secret@example.com",
        "https://example.com/?token=secret",
        "file:///tmp/model",
    ]:
        body.update(revision=changed["revision"], base_url=url)
        assert (
            client.put("/api/provider/settings", json=body, headers=headers).status_code
            == 400
        )


def test_test_action_requires_explicit_synthetic_request(owner):
    client, headers, _ = owner
    assert (
        client.post(
            "/api/provider/test",
            json={"revision": "none", "authorize_synthetic": False},
            headers=headers,
        ).status_code
        == 400
    )


def test_stale_provider_identity_cannot_send_to_changed_configuration(owner):
    import httpx

    from server.songbook.imports.provider_settings import make_provider
    from server.songbook.imports.providers.base import SelectedPage, VisionRequest

    client, headers, _ = owner
    body = configuration(client.get("/api/provider/settings").json()["revision"])
    saved = client.put("/api/provider/settings", json=body, headers=headers).json()
    calls = []
    adapter = make_provider(
        client.app.state.store,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: calls.append(request))
        ),
    )
    body.update(revision=saved["revision"], enabled=False, api_key=None)
    client.put("/api/provider/settings", json=body, headers=headers)
    assert not adapter.status().available
    with pytest.raises(ValueError, match="changed"):
        adapter.convert(VisionRequest([SelectedPage(1, b"png", "hash")]))
    assert calls == []


def test_synthetic_connection_test_uses_saved_endpoint_without_collection(
    owner, monkeypatch
):
    import base64
    import json

    import httpx

    from server.songbook.api import provider as api
    from server.songbook.imports.provider_settings import make_provider

    client, headers, _ = owner
    body = configuration(client.get("/api/provider/settings").json()["revision"])
    body["enabled"] = False
    saved = client.put("/api/provider/settings", json=body, headers=headers).json()
    captured = []

    def respond(request):
        captured.append(request)
        payload = json.loads(request.content)
        image = base64.b64decode(
            payload["messages"][0]["content"][0]["image_url"]["url"].split(",", 1)[1]
        )
        assert image.startswith(b"\x89PNG")
        return httpx.Response(
            200,
            json={
                "id": "synthetic",
                "model": "synthetic-vision",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": '{"source":"{title: Synthetic}","uncertainties":[]}'
                        },
                    }
                ],
            },
        )

    transport = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(
        api,
        "make_provider",
        lambda store, **kwargs: make_provider(store, client=transport, **kwargs),
    )
    response = client.post(
        "/api/provider/test",
        json={"revision": saved["revision"], "authorize_synthetic": True},
        headers=headers,
    )
    assert response.status_code == 200 and len(captured) == 1
    assert "synthetic-provider-secret" not in response.text
    assert not client.get("/api/provider").json()["available"]


def test_provider_secrets_are_excluded_from_both_archive_types(owner, tmp_path):
    import zipfile

    from server.songbook.portability.backup import backup_library
    from server.songbook.portability.export import export_library

    client, headers, _ = owner
    body = configuration(client.get("/api/provider/settings").json()["revision"])
    assert (
        client.put("/api/provider/settings", json=body, headers=headers).status_code
        == 200
    )
    for function, name in [
        (export_library, "portable.zip"),
        (backup_library, "backup.zip"),
    ]:
        path = tmp_path / name
        function(client.app.state.store, path)
        with zipfile.ZipFile(path) as archive:
            assert all(".ai-provider" not in name for name in archive.namelist())
            assert all(
                b"synthetic-provider-secret" not in archive.read(name)
                for name in archive.namelist()
            )


def test_corrupt_configuration_is_reported_without_disclosing_its_contents(owner):
    client, _, root = owner
    (root / ".ai-provider.json").write_text("{synthetic-corrupt-secret")
    response = client.get("/api/provider/settings")
    assert (
        response.status_code == 503 and "synthetic-corrupt-secret" not in response.text
    )
    assert client.get("/api/provider").status_code == 503


def test_changed_endpoint_invalidates_already_queued_ai_consent(owner):
    import io

    import httpx

    from server.songbook.imports.provider_settings import make_provider
    from server.songbook.imports.worker import run_once

    client, headers, _ = owner
    body = configuration(client.get("/api/provider/settings").json()["revision"])
    saved = client.put("/api/provider/settings", json=body, headers=headers).json()
    status = client.get("/api/provider").json()
    store = client.app.state.store
    jobs = client.app.state.imports
    source = store.register_source(
        io.BytesIO(b"synthetic PDF placeholder"), "synthetic.pdf", "pdf"
    )
    job = jobs.enqueue_import(
        source.id,
        [
            {
                "pages": [1],
                "provider": status["provider"],
                "model": status["model"],
                "authorization": True,
            }
        ],
        "ai",
        "revision-guard",
    )
    body.update(
        revision=saved["revision"], base_url="https://changed.example/v1", api_key=None
    )
    client.put("/api/provider/settings", json=body, headers=headers)
    calls = []
    adapter = make_provider(
        store,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: calls.append(request))
        ),
    )
    run_once(jobs, "synthetic-worker", adapter)
    assert jobs.get_job(job["id"])["state"] == "failed" and calls == []


def test_saved_disable_also_invalidates_environment_loaded_provider(owner, monkeypatch):
    from server.songbook.imports.provider_settings import make_provider

    client, headers, _ = owner
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-env-key")
    monkeypatch.setenv("SONGBOOK_ANTHROPIC_MODEL", "synthetic-model")
    monkeypatch.setenv("SONGBOOK_ALLOW_EXTERNAL_AI", "true")
    adapter = make_provider(client.app.state.store)
    config = client.get("/api/provider/settings").json()
    config.pop("has_api_key")
    config.update(enabled=False, api_key=None)
    assert (
        client.put("/api/provider/settings", json=config, headers=headers).status_code
        == 200
    )
    assert not adapter.status().available
    getattr(adapter, "adapter", adapter).client.close()


@pytest.mark.parametrize("key", ["non-ascii-κ", "bad\x00key", "bad\tkey"])
def test_invalid_header_keys_cannot_create_unreadable_configuration(owner, key):
    client, headers, _ = owner
    original = client.get("/api/provider/settings").json()
    body = configuration(original["revision"])
    body["api_key"] = key
    response = client.put("/api/provider/settings", json=body, headers=headers)
    assert response.status_code == 400
    assert (
        client.get("/api/provider/settings").json()["revision"] == original["revision"]
    )
