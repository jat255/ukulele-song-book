import io

import pytest

from server.songbook.storage.arrangements import ConflictError, LibraryStore


def test_source_dedup_preserves_original(tmp_path):
    store = LibraryStore(tmp_path)
    a = store.register_source(io.BytesIO(b"original"), "one.pdf", "pdf")
    b = store.register_source(io.BytesIO(b"original"), "../other.pdf", "pdf")
    assert a.id == b.id
    assert a.path.read_bytes() == b"original"
    assert a.path.is_relative_to(tmp_path)


def test_revision_compare_and_swap(tmp_path):
    store = LibraryStore(tmp_path)
    initial = store.create_arrangement(None, "{title: Test}\n[C]One", [], None)
    edited = store.save_arrangement(
        initial.id, initial.revision, "{title: Test}\n[G]Two"
    )
    with pytest.raises(ConflictError):
        store.save_arrangement(initial.id, initial.revision, "{title: Test}\n[D]Three")
    assert store.get_arrangement(initial.id).revision == edited.revision
    assert (
        store.restore_revision(initial.id, edited.revision, initial.revision).source
        == initial.source
    )


def test_idempotent_acceptance_does_not_overwrite_later_edit(tmp_path):
    store = LibraryStore(tmp_path)
    first = store.create_arrangement(None, "[C]One", [], "job-1")
    edited = store.save_arrangement(first.id, first.revision, "[G]Two")
    retry = store.create_arrangement(None, "[C]One", [], "job-1")
    assert retry.id == first.id
    assert retry.revision == edited.revision
    assert retry.source == edited.source


def test_concurrent_edits_accept_exactly_one(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    store = LibraryStore(tmp_path)
    initial = store.create_arrangement(None, "[C]Original", [], None)

    def save(source):
        try:
            return (
                LibraryStore(tmp_path)
                .save_arrangement(initial.id, initial.revision, source)
                .source
            )
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(save, ["[D]First", "[G]Second"]))
    assert outcomes.count("conflict") == 1
    assert store.get_arrangement(initial.id).source in outcomes


def test_source_registration_reads_all_stream_chunks(tmp_path):
    class Chunked(io.BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 3) if size >= 0 else 3)

    store = LibraryStore(tmp_path)
    record = store.register_source(Chunked(b"full original"), "source.pdf", "pdf")
    assert record.path.read_bytes() == b"full original"


def test_database_context_closes_connection(tmp_path):
    import sqlite3

    from server.songbook.storage.db import connect

    store = LibraryStore(tmp_path)
    with connect(store.database) as db:
        db.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute("SELECT 1")


def test_source_reference_roundtrips(tmp_path):
    store = LibraryStore(tmp_path)
    original = store.register_source(io.BytesIO(b"pdf"), "x.pdf", "pdf")
    snapshot = store.create_arrangement(
        None, "[C]Song", [{"source_id": original.id, "pages": [1, 2]}], None
    )
    assert snapshot.source_refs[0]["source_id"] == original.id
    assert snapshot.source_refs[0]["pages"] == [1, 2]


def test_invalid_source_page_references_are_rejected(tmp_path):
    store = LibraryStore(tmp_path)
    original = store.register_source(io.BytesIO(b"pdf"), "x.pdf", "pdf")
    with pytest.raises(ValueError):
        store.create_arrangement(
            None, "[C]Song", [{"source_id": original.id, "pages": [0]}], None
        )


def test_song_id_must_identify_existing_song(tmp_path):
    store = LibraryStore(tmp_path)
    with pytest.raises((ValueError, KeyError)):
        store.create_arrangement("../arbitrary", "[C]Song", [], None)


def test_corrupted_existing_original_is_not_silently_reused(tmp_path):
    from server.songbook.storage.arrangements import RecoveringError

    store = LibraryStore(tmp_path)
    record = store.register_source(io.BytesIO(b"original"), "one.pdf", "pdf")
    record.path.write_bytes(b"corrupt")
    with pytest.raises(RecoveringError):
        store.register_source(io.BytesIO(b"original"), "two.pdf", "pdf")
