"""Ordered occurrences and optimistic setlist edits."""

import uuid

import pytest

from server.songbook.storage.arrangements import ConflictError, LibraryStore
from server.songbook.storage.setlists import SetlistStore


def test_duplicate_occurrences_reorder_and_conflicts(tmp_path):
    store = LibraryStore(tmp_path)
    a = store.create_arrangement(None, "{title: A}\n[C]A", [], None)
    b = store.create_arrangement(None, "{title: B}\n[G]B", [], None)
    sets = SetlistStore(store)
    playlist = sets.create("My set")
    items = [
        {"id": str(uuid.uuid4()), "arrangementId": ident}
        for ident in (a.id, b.id, a.id)
    ]
    saved = sets.save_setlist(playlist["id"], playlist["revision"], "My set", items)
    assert [item["arrangementId"] for item in saved["items"]] == [a.id, b.id, a.id]
    reordered = sets.save_setlist(
        saved["id"], saved["revision"], "My set", [items[0], items[2], items[1]]
    )
    assert [item["id"] for item in sets.get(saved["id"])["items"]] == [
        items[0]["id"],
        items[2]["id"],
        items[1]["id"],
    ]
    with pytest.raises(ConflictError):
        sets.save_setlist(saved["id"], saved["revision"], "Stale", items)
    assert sets.get(reordered["id"])["revision"] == reordered["revision"]
    sets.delete(reordered["id"], reordered["revision"])
    assert store.get_arrangement(a.id).source == a.source


def test_deleted_arrangement_remains_as_unavailable_occurrence(tmp_path):
    from server.songbook.storage.library import LibraryIndex

    store = LibraryStore(tmp_path)
    item = store.create_arrangement(None, "{title: A}\n[C]A", [], None)
    sets = SetlistStore(store)
    playlist = sets.create("Set")
    saved = sets.save_setlist(
        playlist["id"],
        playlist["revision"],
        "Set",
        [{"id": str(uuid.uuid4()), "arrangementId": item.id}],
    )
    library = LibraryIndex(store)
    library.delete(item.id, library.metadata(item.id)["revision"])
    occurrence = sets.get(saved["id"])["items"][0]
    assert occurrence["arrangementId"] == item.id and occurrence["available"] is False


def test_setlist_api_requires_auth_and_checks_revision(tmp_path):
    from fastapi.testclient import TestClient

    from server.songbook.config import Settings
    from server.songbook.main import create_app

    app = create_app(
        Settings(library_root=tmp_path, allowed_origins=("http://testserver",))
    )
    app.state.auth.set_password("synthetic test password")
    item = app.state.store.create_arrangement(None, "[C]Hello", [], None)
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/setlists").status_code == 401
        auth = client.post(
            "/api/session",
            json={"password": "synthetic test password"},
            headers={"Origin": "http://testserver"},
        )
        headers = {"Origin": "http://testserver", "X-CSRF-Token": auth.json()["csrf"]}
        created = client.post("/api/setlists", json={"title": "Set"}, headers=headers)
        assert created.status_code == 201
        data = created.json()
        occurrence = str(uuid.uuid4())
        body = {
            "revision": data["revision"],
            "title": "Set",
            "items": [{"id": occurrence, "arrangementId": item.id}],
        }
        saved = client.put(f"/api/setlists/{data['id']}", json=body, headers=headers)
        assert saved.status_code == 200
        assert (
            client.put(
                f"/api/setlists/{data['id']}", json=body, headers=headers
            ).status_code
            == 409
        )
        assert (
            client.get(f"/api/setlists/{data['id']}").json()["items"][0]["id"]
            == occurrence
        )


def test_occurrence_ids_cannot_be_reused_across_sets(tmp_path):
    store = LibraryStore(tmp_path)
    song = store.create_arrangement(None, "[C]Hello", [], None)
    sets = SetlistStore(store)
    first = sets.create("One")
    second = sets.create("Two")
    occurrence = {"id": str(uuid.uuid4()), "arrangementId": song.id}
    sets.save_setlist(first["id"], first["revision"], "One", [occurrence])
    with pytest.raises(ValueError):
        sets.save_setlist(second["id"], second["revision"], "Two", [occurrence])
    assert sets.get(second["id"])["items"] == []
