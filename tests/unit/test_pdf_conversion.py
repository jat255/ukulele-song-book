from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from server.songbook.imports.pdf_extract import extract_pages, render_page
from server.songbook.imports.reading_order import order_columns


def test_two_columns_read_down_then_across():
    words = [
        {"text": "L1", "x0": 10, "x1": 30, "top": 10, "bottom": 20},
        {"text": "R1", "x0": 210, "x1": 230, "top": 10, "bottom": 20},
        {"text": "L2", "x0": 10, "x1": 30, "top": 40, "bottom": 50},
        {"text": "R2", "x0": 210, "x1": 230, "top": 40, "bottom": 50},
    ]
    assert [w["text"] for w in order_columns(words, 300)] == ["L1", "L2", "R1", "R2"]


def test_vector_lyrics_are_not_declared_complete(tmp_path):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    stream = DecodedStreamObject()
    stream.set_data(b"10 10 50 4 re f 10 20 50 4 re f")
    page[NameObject("/Contents")] = writer._add_object(stream)
    page[NameObject("/Resources")] = DictionaryObject()
    path = tmp_path / "vector.pdf"
    writer.write(path)
    pages = extract_pages(path, [1])
    assert pages[0].needs_visual_review
    assert render_page(path, 1, 72).startswith(b"\x89PNG")


def test_page_bounds_and_corrupt_input(tmp_path):
    path = tmp_path / "invalid.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(ValueError):
        extract_pages(path, [1])
    with pytest.raises(ValueError):
        render_page(Path(path), 0, 72)


def test_chords_anchor_to_character_positions():
    from server.songbook.imports.convert import attach_chords

    chars = [
        {"text": "W", "x0": 10, "x1": 22},
        {"text": "i", "x0": 22, "x1": 25},
        {"text": "d", "x0": 25, "x1": 32},
        {"text": "e", "x0": 32, "x1": 39},
    ]
    chords = [{"text": "C", "x0": 10}, {"text": "G", "x0": 25}]
    assert attach_chords(chars, chords) == "[C]Wi[G]de"


def test_selected_regions_exclude_other_songs_and_span_pages():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    pages = [
        PageExtraction(
            1,
            100,
            100,
            [],
            [
                {"text": "LEFT", "x0": 5, "x1": 25, "top": 10, "bottom": 20},
                {"text": "RIGHT", "x0": 60, "x1": 80, "top": 10, "bottom": 20},
            ],
        ),
        PageExtraction(
            2,
            100,
            100,
            [],
            [{"text": "NEXT", "x0": 5, "x1": 25, "top": 10, "bottom": 20}],
        ),
    ]
    drafts = convert_pages(
        pages,
        [
            SongRegion("one", "First", [1, 2], {1: (0, 0, 0.5, 1)}),
            SongRegion("two", "Second", [1], {1: (0.5, 0, 1, 1)}),
        ],
    )
    assert "LEFT" in drafts[0].source and "NEXT" in drafts[0].source
    assert "RIGHT" not in drafts[0].source and "RIGHT" in drafts[1].source
    assert all(d.needs_visual_review for d in drafts)


def test_words_on_same_line_remain_together():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    page = PageExtraction(
        1,
        100,
        100,
        [],
        [
            {"text": "Hello", "x0": 5, "x1": 20, "top": 10, "bottom": 20},
            {"text": "there", "x0": 25, "x1": 40, "top": 11, "bottom": 21},
        ],
    )
    assert (
        convert_pages([page], [SongRegion("x", "Song", [1])])[0].source == "Hello there"
    )


def test_draft_pairs_chords_with_proportional_lyric_positions():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    words = [
        {"text": "C", "x0": 10, "x1": 16, "top": 10, "bottom": 18},
        {"text": "G", "x0": 25, "x1": 31, "top": 10, "bottom": 18},
        {"text": "Wide", "x0": 10, "x1": 39, "top": 20, "bottom": 30},
    ]
    chars = [
        {"text": c, "x0": x0, "x1": x1, "top": 20, "bottom": 30}
        for c, x0, x1 in [("W", 10, 22), ("i", 22, 25), ("d", 25, 32), ("e", 32, 39)]
    ]
    page = PageExtraction(1, 100, 100, chars, words)
    assert (
        convert_pages([page], [SongRegion("x", "Song", [1])])[0].source == "[C]Wi[G]de"
    )


def test_tab_lines_keep_literal_spacing():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    lines = ["A|--0--  |", "E|-------|", "C|--0----|", "G|-------|"]
    words, chars = [], []
    for row, text in enumerate(lines):
        top = 10 + row * 10
        words.append(
            {"text": text, "x0": 5, "x1": 5 + len(text), "top": top, "bottom": top + 8}
        )
        chars.extend(
            {"text": c, "x0": 5 + i, "x1": 6 + i, "top": top, "bottom": top + 8}
            for i, c in enumerate(text)
        )
    draft = convert_pages(
        [PageExtraction(1, 100, 100, chars, words)], [SongRegion("x", "Song", [1])]
    )[0]
    assert "{start_of_tab}\n" + "\n".join(lines) + "\n{end_of_tab}" in draft.source


def test_full_width_heading_does_not_destroy_column_order():
    words = [
        {"text": "HEADER", "x0": 10, "x1": 290, "top": 0, "bottom": 8},
        {"text": "L1", "x0": 10, "x1": 30, "top": 10, "bottom": 20},
        {"text": "R1", "x0": 210, "x1": 230, "top": 10, "bottom": 20},
        {"text": "L2", "x0": 10, "x1": 30, "top": 40, "bottom": 50},
        {"text": "R2", "x0": 210, "x1": 230, "top": 40, "bottom": 50},
    ]
    assert [w["text"] for w in order_columns(words, 300)] == [
        "HEADER",
        "L1",
        "L2",
        "R1",
        "R2",
    ]


def test_draft_retains_source_reference_and_region():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    page = PageExtraction(1, 100, 100, [], [])
    draft = convert_pages(
        [page], [SongRegion("x", "Song", [1], {1: (0, 0, 0.5, 1)}, "abc123")]
    )[0]
    assert draft.source_refs == [
        {"source_hash": "abc123", "page": 1, "rectangle": (0, 0, 0.5, 1)}
    ]
    assert draft.needs_visual_review


def test_encrypted_pdf_requires_explicit_handling(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("private")
    path = tmp_path / "locked.pdf"
    writer.write(path)
    with pytest.raises(ValueError):
        extract_pages(path, [1])


def test_oversized_page_render_is_rejected(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=10000, height=10000)
    path = tmp_path / "huge.pdf"
    writer.write(path)
    with pytest.raises(ValueError):
        render_page(path, 1, 300)


def test_vector_only_content_does_not_become_an_accepted_empty_song(tmp_path):
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    draft = convert_pages(
        [PageExtraction(1, 200, 200, [], [])],
        [SongRegion("x", "Song", [1], source_hash="source")],
    )[0]
    assert draft.needs_visual_review
    assert draft.source_refs[0]["source_hash"] == "source"
    assert any("no text" in message.lower() for message in draft.diagnostics)


def test_verified_chordpro_is_preferred_to_pdf_draft():
    from server.songbook.imports.convert import preferred_source

    assert (
        preferred_source("verified source", "extracted draft", True)
        == "verified source"
    )
    assert (
        preferred_source("unverified source", "extracted draft", False)
        == "extracted draft"
    )


def test_rotated_text_is_flagged_for_review(tmp_path):
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject(
        {
            NameObject("/F1"): DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
        }
    )
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): font})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 0 1 -1 0 100 10 Tm (Hello) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "rotated.pdf"
    writer.write(path)
    extracted = extract_pages(path, [1])[0]
    assert any("rotat" in message.lower() for message in extracted.diagnostics)


def test_extraction_diagnostics_reach_draft():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    page = PageExtraction(
        1, 100, 100, [], [], diagnostics=["Rotated text requires review"]
    )
    draft = convert_pages([page], [SongRegion("x", "Song", [1])])[0]
    assert "Rotated text requires review" in draft.diagnostics


def test_invalid_regions_are_rejected():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    page = PageExtraction(1, 100, 100, [], [])
    for region in [
        SongRegion("a", "A", []),
        SongRegion("a", "A", [2]),
        SongRegion("a", "A", [1], {1: (0, 0, 2, 1)}),
    ]:
        with pytest.raises(ValueError):
            convert_pages([page], [region])


def test_draft_uncertainty_covers_inferred_content():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    page = PageExtraction(
        1, 100, 100, [], [{"text": "hello", "x0": 1, "x1": 10, "top": 1, "bottom": 5}]
    )
    draft = convert_pages([page], [SongRegion("x", "Song", [1])])[0]
    assert draft.uncertainty_spans == [
        {"start": 0, "end": len(draft.source), "reason": "unverified extraction"}
    ]


def test_uncertainty_offsets_use_utf16():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    page = PageExtraction(
        1, 100, 100, [], [{"text": "🌻", "x0": 1, "x1": 10, "top": 1, "bottom": 5}]
    )
    assert (
        convert_pages([page], [SongRegion("x", "Song", [1])])[0].uncertainty_spans[0][
            "end"
        ]
        == 2
    )


def test_columns_tolerate_a_heading_crossing_the_gutter():
    words = [{"text": "heading", "x0": 70, "x1": 230, "top": 0, "bottom": 8}]
    words += [
        {
            "text": f"{side}{i}",
            "x0": x,
            "x1": x + 30,
            "top": 10 + i * 15,
            "bottom": 20 + i * 15,
        }
        for i in range(4)
        for side, x in [("L", 10), ("R", 210)]
    ]
    assert [w["text"] for w in order_columns(words, 300)] == [
        "heading",
        "L0",
        "L1",
        "L2",
        "L3",
        "R0",
        "R1",
        "R2",
        "R3",
    ]


def test_columns_report_uncertainty_when_content_crosses_gutter():
    from server.songbook.imports.convert import convert_pages
    from server.songbook.imports.models import PageExtraction, SongRegion

    words = [
        {
            "text": f"{side}{i}",
            "x0": x,
            "x1": x + 30,
            "top": 10 + i * 15,
            "bottom": 20 + i * 15,
        }
        for i in range(4)
        for side, x in [("L", 10), ("R", 210)]
    ]
    words.append({"text": "cross", "x0": 100, "x1": 200, "top": 35, "bottom": 45})
    draft = convert_pages(
        [PageExtraction(1, 300, 200, [], words)], [SongRegion("x", "Song", [1])]
    )[0]
    assert draft.needs_visual_review
    assert draft.source_refs


def test_columns_with_a_single_gutter_crossing_word():
    words = [
        {
            "text": f"{side}{i}",
            "x0": x,
            "x1": x + 30,
            "top": 20 + i * 15,
            "bottom": 30 + i * 15,
        }
        for i in range(4)
        for side, x in [("L", 10), ("R", 210)]
    ]
    words.append({"text": "cross", "x0": 100, "x1": 200, "top": 5, "bottom": 15})
    assert [w["text"] for w in order_columns(words, 300)] == [
        "cross",
        "L0",
        "L1",
        "L2",
        "L3",
        "R0",
        "R1",
        "R2",
        "R3",
    ]


def test_corpus_job_deadline_is_enforced():
    import time

    from tools.convert_corpus import job_deadline

    with pytest.raises(TimeoutError), job_deadline(0.02):
        time.sleep(1)
