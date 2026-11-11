import hashlib

import pytest

from server.songbook.storage.arrangements import LibraryStore


@pytest.mark.parametrize(
    "point", ["after_intent", "after_revision", "after_replace", "after_index"]
)
def test_recovery_has_matching_file_revision_and_search_index(tmp_path, point):
    store = LibraryStore(tmp_path)
    old = store.create_arrangement(None, "{title: Old}\n[C]ORIGINAL", [], None)

    def crash(stage):
        if stage == point:
            raise RuntimeError("injected crash")

    store.crash_hook = crash
    with pytest.raises(RuntimeError):
        store.save_arrangement(old.id, old.revision, "{title: New}\n[G]UPDATED")
    restored = LibraryStore(tmp_path)
    restored.recover_pending_writes()
    result = restored.get_arrangement(old.id)
    assert hashlib.sha256(result.source.encode()).hexdigest() == result.revision
    assert restored.canonical_path(old.id).read_bytes().decode() == result.source
    assert restored.indexed_revision(old.id) == result.revision
    assert result.source in (old.source, "{title: New}\n[G]UPDATED")


def test_initial_acceptance_recovers_when_crashed_before_revision_write(tmp_path):
    store = LibraryStore(tmp_path)

    def crash(stage):
        if stage == "after_intent":
            raise RuntimeError("injected")

    store.crash_hook = crash
    with pytest.raises(RuntimeError):
        store.create_arrangement(None, "[C]First", [], "acceptance")
    restarted = LibraryStore(tmp_path)
    restarted.recover_pending_writes()
    result = restarted.create_arrangement(None, "[C]First", [], "acceptance")
    assert result.source == "[C]First"


def test_crash_before_initial_intent_does_not_leave_dangling_acceptance(tmp_path):
    store = LibraryStore(tmp_path)

    def crash(stage):
        if stage == "before_intent":
            raise RuntimeError("injected")

    store.crash_hook = crash
    with pytest.raises(RuntimeError):
        store.create_arrangement(None, "[C]First", [], "acceptance")
    restarted = LibraryStore(tmp_path)
    restarted.recover_pending_writes()
    result = restarted.create_arrangement(None, "[C]First", [], "acceptance")
    assert result.source == "[C]First"


def test_recovery_search_index_matches_accepted_source(tmp_path):
    from server.songbook.storage.db import connect

    store = LibraryStore(tmp_path)
    old = store.create_arrangement(None, "{title: Old}\n[C]ORIGINAL", [], None)

    def crash(stage):
        if stage == "after_replace":
            raise RuntimeError("injected")

    store.crash_hook = crash
    with pytest.raises(RuntimeError):
        store.save_arrangement(old.id, old.revision, "{title: New}\n[G]UPDATED")
    restarted = LibraryStore(tmp_path)
    restarted.recover_pending_writes()
    snapshot = restarted.get_arrangement(old.id)
    with connect(restarted.database) as db:
        rows = db.execute(
            "SELECT arrangement_id FROM arrangement_search WHERE arrangement_search MATCH ?",
            ("UPDATED",),
        ).fetchall()
        assert [row["arrangement_id"] for row in rows] == [snapshot.id]
        assert not db.execute(
            "SELECT arrangement_id FROM arrangement_search WHERE arrangement_search MATCH ?",
            ("ORIGINAL",),
        ).fetchall()
        stored = db.execute(
            "SELECT parsed_json FROM arrangements WHERE id=?", (snapshot.id,)
        ).fetchone()
    import json

    assert json.loads(stored["parsed_json"])["source"] == snapshot.source


def test_failed_canonical_replace_stays_recoverable(tmp_path, monkeypatch):
    from server.songbook.storage import arrangements

    store = LibraryStore(tmp_path)
    old = store.create_arrangement(None, "[C]OLD", [], None)
    original = arrangements.atomic_write

    def fail(path, data):
        if path.name == "song.chordpro":
            raise OSError("disk full")
        return original(path, data)

    monkeypatch.setattr(arrangements, "atomic_write", fail)
    with pytest.raises(OSError):
        store.save_arrangement(old.id, old.revision, "[G]NEW")
    with pytest.raises(arrangements.RecoveringError):
        store.get_arrangement(old.id)
    monkeypatch.setattr(arrangements, "atomic_write", original)
    store.recover_pending_writes()
    assert store.get_arrangement(old.id).source == "[G]NEW"


def test_inconsistent_parsed_index_is_never_served(tmp_path):
    import json

    from server.songbook.storage.arrangements import RecoveringError
    from server.songbook.storage.db import connect

    store = LibraryStore(tmp_path)
    snapshot = store.create_arrangement(None, "[C]NEW", [], None)
    with connect(store.database) as db:
        db.execute(
            "UPDATE arrangements SET parsed_json=? WHERE id=?",
            (json.dumps({"source": "stale"}), snapshot.id),
        )
    with pytest.raises(RecoveringError):
        store.get_arrangement(snapshot.id)
    store.recover_pending_writes()
    assert store.get_arrangement(snapshot.id).document["source"] == snapshot.source


def test_missing_canonical_is_recovered_from_accepted_revision(tmp_path):
    from server.songbook.storage.arrangements import RecoveringError

    store = LibraryStore(tmp_path)
    snapshot = store.create_arrangement(None, "[C]Saved", [], None)
    store.canonical_path(snapshot.id).unlink()
    with pytest.raises(RecoveringError):
        store.get_arrangement(snapshot.id)
    store.recover_pending_writes()
    assert store.get_arrangement(snapshot.id).source == snapshot.source


def test_recovery_rejects_corrupt_journal_metadata(tmp_path):
    import json

    from server.songbook.storage.arrangements import RecoveringError
    from server.songbook.storage.db import connect

    store = LibraryStore(tmp_path)
    old = store.create_arrangement(None, "[C]OLD", [], None)

    def crash(stage):
        if stage == "after_revision":
            raise RuntimeError("injected")

    store.crash_hook = crash
    with pytest.raises(RuntimeError):
        store.save_arrangement(old.id, old.revision, "[G]NEW")
    with connect(store.database) as db:
        db.execute(
            "UPDATE write_intents SET parsed_json=? WHERE arrangement_id=?",
            (json.dumps({"schemaVersion": 1, "source": "[D]WRONG"}), old.id),
        )
    with pytest.raises(RecoveringError):
        store.recover_pending_writes()
    with pytest.raises(RecoveringError):
        store.get_arrangement(old.id)
