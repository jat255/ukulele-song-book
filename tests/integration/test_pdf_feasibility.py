from pathlib import Path

from pypdf import PdfReader

from server.songbook.pdf.models import PdfRenderRequest
from server.songbook.pdf.render import render_pdf


def test_pdf_complete_at_selected_size(tmp_path: Path):
    request = PdfRenderRequest(
        source="{title: Test}\n{sov: Verse}\n[C]LINE-ONE\n[G]LINE-TWO\n{eov}",
        output_dir=tmp_path,
        paper="Letter",
        font_pt=12,
        columns=1,
    )
    artifact = render_pdf(request)
    reader = PdfReader(artifact.path)
    text = " ".join(page.extract_text() for page in reader.pages)
    assert "LINE-ONE" in text and "LINE-TWO" in text
    assert round(float(reader.pages[0].mediabox.width)) == 612
    assert round(float(reader.pages[0].mediabox.height)) == 792
    assert artifact.page_count == len(reader.pages)


def test_a4_pdf_embeds_fonts_and_preserves_repeats(tmp_path):
    request = PdfRenderRequest(
        source="{title: Example}\n[C]REPEATED\n[C]REPEATED\n",
        output_dir=tmp_path,
        paper="A4",
        font_pt=12,
        columns=1,
    )
    artifact = render_pdf(request)
    reader = PdfReader(artifact.path)
    assert round(float(reader.pages[0].mediabox.width)) == 595
    assert round(float(reader.pages[0].mediabox.height)) == 842
    assert "".join(p.extract_text() for p in reader.pages).count("REPEATED") == 2
    fonts = reader.pages[0]["/Resources"]["/Font"].get_object()
    assert fonts
    descriptors = []
    for font in fonts.values():
        obj = font.get_object()
        if obj.get("/Subtype") == "/Type3":
            assert obj.get("/CharProcs")
            continue
        if "/DescendantFonts" in obj:
            obj = obj["/DescendantFonts"][0].get_object()
        if "/FontDescriptor" in obj:
            descriptors.append(obj["/FontDescriptor"].get_object())
    assert descriptors and all(
        any(key in desc for key in ("/FontFile", "/FontFile2", "/FontFile3"))
        for desc in descriptors
    )


def test_wide_tab_reports_infeasible(tmp_path):
    import pytest

    request = PdfRenderRequest(
        source="{sot}\nA|" + "-" * 300 + "|\n{eot}",
        output_dir=tmp_path,
        paper="Letter",
        font_pt=12,
        columns=2,
    )
    with pytest.raises(ValueError, match="Tab exceeds"):
        render_pdf(request)


def test_auto_columns_use_fewest_actual_pages(tmp_path):
    source = "{title: Example}\n" + "\n".join(f"[C]LINE-{i:03d}" for i in range(95))
    one = render_pdf(PdfRenderRequest(source=source, output_dir=tmp_path, columns=1))
    two = render_pdf(PdfRenderRequest(source=source, output_dir=tmp_path, columns=2))
    auto = render_pdf(
        PdfRenderRequest(source=source, output_dir=tmp_path, columns="auto")
    )
    assert auto.page_count == min(one.page_count, two.page_count)
    assert auto.columns == (1 if one.page_count <= two.page_count else 2)


def test_long_sections_keep_all_lines_in_order(tmp_path):
    source = (
        "{title: Long}\n{sov: Heading}\n"
        + "\n".join(f"[C]LINE-{i:03d}" for i in range(140))
        + "\n{eov}"
    )
    artifact = render_pdf(
        PdfRenderRequest(source=source, output_dir=tmp_path, columns=2)
    )
    text = " ".join(p.extract_text() for p in PdfReader(artifact.path).pages)
    positions = [text.find(f"LINE-{i:03d}") for i in range(140)]
    assert all(p >= 0 for p in positions)
    assert positions == sorted(positions)
    assert "Heading" in text


def test_oversized_lyric_is_reported_instead_of_clipped(tmp_path):
    import pytest

    source = "[C]" + "W" * 400
    with pytest.raises(ValueError, match="exceeds"):
        render_pdf(PdfRenderRequest(source=source, output_dir=tmp_path, columns=1))


def test_auto_columns_fall_back_when_lyric_does_not_fit_two_columns(tmp_path):
    source = "[C]" + "W" * 35
    artifact = render_pdf(
        PdfRenderRequest(source=source, output_dir=tmp_path, columns="auto")
    )
    assert artifact.columns == 1


def test_long_tab_preserves_complete_groups(tmp_path):
    groups = []
    for i in range(40):
        groups.extend(
            [
                f"A|--{i:02d}--|",
                f"E|--{i:02d}--|",
                f"C|--{i:02d}--|",
                f"G|--{i:02d}--|",
                "",
            ]
        )
    source = "{sot}\n" + "\n".join(groups) + "\n{eot}"
    artifact = render_pdf(
        PdfRenderRequest(source=source, output_dir=tmp_path, columns=1)
    )
    reader = PdfReader(artifact.path)
    for i in range(40):
        assert any(
            all(f"{s}|--{i:02d}--|" in page.extract_text() for s in "AECG")
            for page in reader.pages
        )


def test_section_heading_stays_with_first_line(tmp_path):
    filler = "\n".join(f"[C]FILL-{i:03d}" for i in range(32))
    source = f"{filler}\n{{sov: SpecialHeading}}\n[C]FIRST-VERSE-LINE\n{{eov}}"
    artifact = render_pdf(
        PdfRenderRequest(source=source, output_dir=tmp_path, columns=1)
    )
    pages = [page.extract_text() for page in PdfReader(artifact.path).pages]
    assert any(
        "SpecialHeading" in text and "FIRST-VERSE-LINE" in text for text in pages
    )


def test_oversized_unchorded_lyric_is_reported(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="exceeds"):
        render_pdf(PdfRenderRequest(source="W" * 400, output_dir=tmp_path, columns=1))


def test_pdf_request_can_use_frozen_snapshot_and_settings(tmp_path):
    from server.songbook.pdf.models import (
        ArrangementSnapshot,
        PerformanceSettings,
        PrintSettings,
    )

    snapshot = ArrangementSnapshot(
        id="a",
        song_id="s",
        revision="r",
        source="{title: Snapshot}\n[C]FROZEN",
        source_refs=[],
    )
    request = PdfRenderRequest(
        output_dir=tmp_path,
        snapshots=[snapshot],
        performance=PerformanceSettings(),
        settings=PrintSettings(paper="A4", font_pt=12, columns=1),
    )
    artifact = render_pdf(request)
    assert "FROZEN" in "".join(p.extract_text() for p in PdfReader(artifact.path).pages)
    assert round(float(PdfReader(artifact.path).pages[0].mediabox.width)) == 595


def test_extracted_pdf_retains_each_chord_lyric_fragment(tmp_path):
    source = "[C]ABCfoo[D]BARbaz [G]GAMMAqux\n[C]NEXTline[D]TAILend"
    artifact = render_pdf(
        PdfRenderRequest(source=source, output_dir=tmp_path, columns=1)
    )
    text = " ".join(p.extract_text() for p in PdfReader(artifact.path).pages)
    for fragment in ("ABCfoo", "BARbaz", "GAMMAqux", "NEXTline", "TAILend"):
        assert fragment in text


def test_ligatures_are_readable_after_unicode_normalization(tmp_path):
    import unicodedata

    artifact = render_pdf(
        PdfRenderRequest(source="[C]office [G]flight", output_dir=tmp_path)
    )
    text = unicodedata.normalize(
        "NFKD", " ".join(p.extract_text() for p in PdfReader(artifact.path).pages)
    )
    assert "office" in text and "flight" in text
