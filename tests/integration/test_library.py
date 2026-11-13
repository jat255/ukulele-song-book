"""Library search, metadata concurrency, variants and retention."""

import io

import pytest

from server.songbook.storage.arrangements import ConflictError, LibraryStore
from server.songbook.storage.library import LibraryIndex


def make_library(tmp_path):
    store = LibraryStore(tmp_path)
    source = store.register_source(io.BytesIO(b"original"), "source.cho", "cho")
    first = store.create_arrangement(
        None,
        "{title: Café Waltz}\n{artist: Example}\n[C#m]Hello moon",
        [{"source_id": source.id, "pages": []}],
        None,
    )
    second = store.create_arrangement(
        first.song_id, "{title: Café Waltz}\n[G]Variant", [], None
    )
    return store, LibraryIndex(store), first, second, source


def test_search_fields_safe_literals_and_variants(tmp_path):
    _, library, first, second, _ = make_library(tmp_path)
    assert {item["id"] for item in library.search_library("Café", [], False)} == {
        first.id,
        second.id,
    }
    assert [item["id"] for item in library.search_library("moon", [], False)] == [
        first.id
    ]
    assert [item["id"] for item in library.search_library("Example", [], False)] == [
        first.id
    ]
    assert [item["id"] for item in library.search_library("C#m", [], False)] == [
        first.id
    ]
    assert library.search_library('" OR *', [], False) == []
    metadata = library.metadata(first.id)
    library.update_metadata(
        first.id,
        metadata["revision"],
        favorite=True,
        tags=["practice"],
        notes="remember",
    )
    assert [item["id"] for item in library.search_library("", ["practice"], True)] == [
        first.id
    ]


def test_metadata_compare_and_swap_and_tombstone_preserves_sources(tmp_path):
    store, library, first, _, source = make_library(tmp_path)
    initial = library.metadata(first.id)
    updated = library.update_metadata(
        first.id, initial["revision"], favorite=True, tags=["été"], notes="practice"
    )
    with pytest.raises(ConflictError):
        library.update_metadata(
            first.id, initial["revision"], favorite=False, tags=[], notes="stale"
        )
    library.delete(first.id, updated["revision"])
    assert first.id not in {
        item["id"] for item in library.search_library("", [], False)
    }
    assert store.get_arrangement(first.id).source == first.source
    assert source.path.read_bytes() == b"original"


def test_played_updates_recent_metadata(tmp_path):
    _, library, first, _, _ = make_library(tmp_path)
    assert library.metadata(first.id)["last_played"] is None
    library.mark_played(first.id)
    assert library.metadata(first.id)["last_played"] is not None


def test_search_includes_tag_text(tmp_path):
    _, library, first, _, _ = make_library(tmp_path)
    metadata = library.metadata(first.id)
    library.update_metadata(
        first.id, metadata["revision"], favorite=False, tags=["strumming"], notes=""
    )
    assert [item["id"] for item in library.search_library("strumming", [], False)] == [
        first.id
    ]


def test_library_api_metadata_variants_export_and_delete(tmp_path):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.main import create_app

    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    item = app.state.store.create_arrangement(
        None, "{title: Test}\n[C]Hi\n{future: preserve}", [], None
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/library").status_code == 401
        login = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": login.json()["csrf"]}
        entries = client.get("/api/library").json()
        assert entries[0]["id"] == item.id
        update = client.patch(
            f"/api/arrangements/{item.id}/metadata",
            json={
                "revision": entries[0]["metadata_revision"],
                "favorite": True,
                "tags": ["warmup"],
                "notes": "slow",
            },
            headers=headers,
        )
        assert update.status_code == 200
        stale = client.patch(
            f"/api/arrangements/{item.id}/metadata",
            json={
                "revision": entries[0]["metadata_revision"],
                "favorite": False,
                "tags": [],
                "notes": "",
            },
            headers=headers,
        )
        assert stale.status_code == 409
        variant = client.post(
            f"/api/songs/{item.song_id}/arrangements",
            json={"source": item.source},
            headers=headers,
        )
        assert variant.status_code == 201
        assert (
            variant.json()["id"] != item.id
            and variant.json()["song_id"] == item.song_id
        )
        export = client.get(f"/api/arrangements/{item.id}/download")
        assert export.content == item.source.encode()
        deleted = client.request(
            "DELETE",
            f"/api/arrangements/{item.id}",
            json={"revision": update.json()["revision"]},
            headers=headers,
        )
        assert deleted.status_code == 204
        assert item.id not in {
            entry["id"] for entry in client.get("/api/library").json()
        }
        assert (
            client.get(f"/api/arrangements/{item.id}").json()["source"] == item.source
        )


def test_metadata_endpoint_reads_independent_revision(tmp_path):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.main import create_app

    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    item = app.state.store.create_arrangement(None, "{title: Test}\n[C]Hi", [], None)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        response = client.get(f"/api/arrangements/{item.id}/metadata")
        assert response.status_code == 200
        assert response.json()["revision"] == 1
        assert response.json()["notes"] == ""


def test_search_combines_tag_and_song_terms(tmp_path):
    _, library, first, _, _ = make_library(tmp_path)
    metadata = library.metadata(first.id)
    library.update_metadata(
        first.id, metadata["revision"], favorite=False, tags=["strumming"], notes=""
    )
    assert [
        item["id"] for item in library.search_library("Café strumming", [], False)
    ] == [first.id]


def test_recent_filter_orders_played_arrangements(tmp_path):
    _, library, first, second, _ = make_library(tmp_path)
    library.mark_played(first.id)
    assert [
        item["id"] for item in library.search_library("", [], False, recent=True)
    ] == [first.id]
    library.mark_played(second.id)
    assert [
        item["id"] for item in library.search_library("", [], False, recent=True)
    ] == [second.id, first.id]


def test_unattached_original_is_visible_as_source_only(tmp_path):
    store, library, _, _, _ = make_library(tmp_path)
    source = store.register_source(io.BytesIO(b"unconverted"), "Unique Book.pdf", "pdf")
    result = library.search_library("Unique", [], False)
    assert any(item["id"] == source.id and item["source_only"] for item in result)


def test_variant_can_retain_original_source_references(tmp_path):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.main import create_app

    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    source = app.state.store.register_source(io.BytesIO(b"original"), "book.pdf", "pdf")
    item = app.state.store.create_arrangement(
        None, "[C]Music", [{"source_id": source.id, "pages": [3]}], None
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        response = client.post(
            f"/api/songs/{item.song_id}/arrangements",
            json={"source": "[D]Music", "source_arrangement_id": item.id},
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": auth.json()["csrf"],
            },
        )
        assert response.status_code == 201
        assert response.json()["source_refs"][0]["source_id"] == source.id
        assert response.json()["source_refs"][0]["pages"] == [3]


def test_source_only_entry_can_be_removed_without_deleting_original(tmp_path):
    from server.songbook.storage.db import connect

    store = LibraryStore(tmp_path)
    index = LibraryIndex(store)
    source = store.register_source(io.BytesIO(b"synthetic PDF"), "only.pdf", "pdf")
    entry = next(
        item for item in index.search_library("", [], False) if item["id"] == source.id
    )
    index.delete_source(source.id, entry["metadata_revision"])
    assert all(item["id"] != source.id for item in index.search_library("", [], False))
    with connect(store.database) as db:
        path = db.execute(
            "SELECT path FROM sources WHERE id=?", (source.id,)
        ).fetchone()[0]
    assert (store.root / path).read_bytes() == b"synthetic PDF"
    with pytest.raises(ConflictError):
        index.delete_source(source.id, entry["metadata_revision"])


def test_source_delete_rejects_new_arrangement_link(tmp_path):
    store = LibraryStore(tmp_path)
    index = LibraryIndex(store)
    source = store.register_source(io.BytesIO(b"original"), "linked.pdf", "pdf")
    entry = next(
        item for item in index.search_library("", [], False) if item["id"] == source.id
    )
    store.create_arrangement(
        None,
        "{title: Linked}\n[C]Synthetic",
        [{"source_id": source.id, "pages": [1]}],
        None,
    )
    with pytest.raises(ConflictError):
        index.delete_source(source.id, entry["metadata_revision"])


def test_deleted_source_stays_hidden_after_portable_restore(tmp_path):
    from server.songbook.portability.export import export_library
    from server.songbook.portability.restore import restore_archive

    store = LibraryStore(tmp_path / "library")
    index = LibraryIndex(store)
    source = store.register_source(
        io.BytesIO(b"synthetic retained PDF"), "hidden.pdf", "pdf"
    )
    index.delete_source(source.id, 0)
    archive = tmp_path / "portable.zip"
    export_library(store, archive)
    destination = tmp_path / "restored"
    restore_archive(archive, destination, "portable")
    restored = LibraryStore(destination)
    assert all(
        item["id"] != source.id
        for item in LibraryIndex(restored).search_library("", [], False)
    )


def test_source_library_delete_api_requires_auth_and_csrf(tmp_path):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.main import create_app

    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    source = app.state.store.register_source(
        io.BytesIO(b"synthetic source"), "delete.pdf", "pdf"
    )
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        path = f"/api/sources/{source.id}/library"
        assert client.request("DELETE", path, json={"revision": 0}).status_code == 401
        session = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        ).json()
        assert client.request("DELETE", path, json={"revision": 0}).status_code == 403
        headers = {"Origin": "http://testserver", "X-CSRF-Token": session["csrf"]}
        assert (
            client.request(
                "DELETE", path, json={"revision": 0}, headers=headers
            ).status_code
            == 204
        )
        assert (
            client.request(
                "DELETE", path, json={"revision": 0}, headers=headers
            ).status_code
            == 409
        )
        assert client.get(f"/api/sources/{source.id}/original").status_code == 200
