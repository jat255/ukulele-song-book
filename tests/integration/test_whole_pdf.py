import io

import pytest
from pypdf import PdfWriter

from server.songbook.imports.jobs import ImportJobs
from server.songbook.storage.arrangements import LibraryStore


def pdf_source(store, pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return store.register_source(buffer, "whole.pdf", "pdf")


def test_entire_pdf_becomes_one_ordered_song_selection(tmp_path):
    store = LibraryStore(tmp_path)
    jobs = ImportJobs(store)
    source = pdf_source(store, 3)
    job = jobs.enqueue_import(source.id, [{"all_pages": True}], "local", "all")
    assert len(job["selection"]) == 1 and job["selection"][0]["pages"] == [1, 2, 3]
    assert "all_pages" not in job["selection"][0]
    assert (
        jobs.enqueue_import(source.id, [{"all_pages": True}], "local", "all")["id"]
        == job["id"]
    )


def test_entire_pdf_ai_limit_rejects_without_truncation(tmp_path):
    store = LibraryStore(tmp_path)
    jobs = ImportJobs(store)
    source = pdf_source(store, 6)
    with pytest.raises(ValueError, match="five|5"):
        jobs.enqueue_import(
            source.id,
            [
                {
                    "all_pages": True,
                    "provider": "synthetic",
                    "model": "test",
                    "authorization": True,
                }
            ],
            "ai",
            "large",
        )
    assert jobs.claim_job("worker") is None


def test_full_pdf_crop_is_applied_to_every_page(tmp_path):
    store = LibraryStore(tmp_path)
    jobs = ImportJobs(store)
    source = pdf_source(store, 2)
    crop = [0, 0, 0.5, 1]
    job = jobs.enqueue_import(
        source.id, [{"all_pages": True, "crop": crop}], "local", "crop"
    )
    assert job["selection"][0]["rectangles"] == {"1": crop, "2": crop}
