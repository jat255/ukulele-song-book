import hashlib
import json

import pytest

from tools.corpus import inventory, select_corpus


def digest(data):
    return hashlib.sha256(data).hexdigest()


def test_supported_files_and_sidecars(tmp_path):
    for name in ("a.PDF", "b.cho", "c.chordpro", "d.txt", "._a.pdf", ".hidden.pdf"):
        (tmp_path / name).write_bytes(b"content")
    (tmp_path / "folder.pdf").mkdir()
    assert {item.relative_path for item in inventory(tmp_path)} == {
        "a.PDF",
        "b.cho",
        "c.chordpro",
    }


def test_no_symlink_escape_or_source_write(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "a.cho").write_bytes(b"song")
    (root / "b.cho").write_bytes(b"song")
    outside = tmp_path / "outside.cho"
    outside.write_bytes(b"private")
    (root / "escape.cho").symlink_to(outside)
    with pytest.raises(ValueError):
        inventory(root)
    (root / "escape.cho").unlink()
    manifest = tmp_path / "selection.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "id": "one",
                        "category": "chordpro",
                        "relative_path": name,
                        "sha256": digest(b"song"),
                        "pages": [1],
                        "expected_observations": "",
                        "verification_status": "pending",
                    }
                    for name in ("a.cho", "b.cho")
                ]
            }
        )
    )
    result = select_corpus(root, manifest, tmp_path / "output")
    assert len(result.samples) == 1
    assert result.samples[0].aliases == ["b.cho"]
    assert (root / "a.cho").read_bytes() == (root / "b.cho").read_bytes() == b"song"


def test_selection_requires_valid_pages_and_hash(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "a.cho").write_bytes(b"song")
    manifest = tmp_path / "selection.json"
    sample = {
        "id": "one",
        "category": "chordpro",
        "relative_path": "a.cho",
        "sha256": digest(b"song"),
        "pages": [1],
        "expected_observations": "",
        "verification_status": "pending",
    }
    for changes in ({"pages": []}, {"pages": [0]}, {"sha256": "0" * 64}):
        manifest.write_text(json.dumps({"samples": [{**sample, **changes}]}))
        with pytest.raises(ValueError):
            select_corpus(root, manifest, tmp_path / "output")


def test_output_cannot_be_inside_source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "a.cho").write_bytes(b"song")
    manifest = tmp_path / "selection.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "id": "one",
                        "category": "chordpro",
                        "relative_path": "a.cho",
                        "sha256": digest(b"song"),
                        "pages": [1],
                        "expected_observations": "",
                        "verification_status": "pending",
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError):
        select_corpus(root, manifest, root / "output")


def test_pdf_pages_must_exist(tmp_path):
    from pypdf import PdfWriter

    root = tmp_path / "source"
    root.mkdir()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    path = root / "a.pdf"
    writer.write(path)
    manifest = tmp_path / "selection.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "id": "one",
                        "category": "pdf",
                        "relative_path": "a.pdf",
                        "sha256": digest(path.read_bytes()),
                        "pages": [2],
                        "expected_observations": "",
                        "verification_status": "pending",
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError):
        select_corpus(root, manifest, tmp_path / "output")


def test_selection_never_follows_destination_symlink(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    original = root / "a.cho"
    original.write_bytes(b"song")
    output = tmp_path / "output"
    (output / "originals").mkdir(parents=True)
    (output / "originals" / (digest(b"song") + ".cho")).symlink_to(original)
    manifest = tmp_path / "selection.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "id": "one",
                        "category": "chordpro",
                        "relative_path": "a.cho",
                        "sha256": digest(b"song"),
                        "pages": [1],
                        "expected_observations": "",
                        "verification_status": "pending",
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError):
        select_corpus(root, manifest, output)
    assert original.read_bytes() == b"song"


def test_selection_never_follows_manifest_symlink(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    original = root / "a.cho"
    original.write_bytes(b"song")
    output = tmp_path / "output"
    output.mkdir()
    (output / "manifest.json").symlink_to(original)
    selection = tmp_path / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "id": "one",
                        "category": "chordpro",
                        "relative_path": "a.cho",
                        "sha256": digest(b"song"),
                        "pages": [1],
                        "expected_observations": "",
                        "verification_status": "pending",
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError):
        select_corpus(root, selection, output)
    assert original.read_bytes() == b"song"


def test_existing_hardlinked_output_cannot_modify_other_source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "a.cho").write_bytes(b"song")
    other = root / "other.cho"
    other.write_bytes(b"other")
    output = tmp_path / "output"
    (output / "originals").mkdir(parents=True)
    import os

    os.link(other, output / "originals" / (digest(b"song") + ".cho"))
    selection = tmp_path / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "id": "one",
                        "category": "chordpro",
                        "relative_path": "a.cho",
                        "sha256": digest(b"song"),
                        "pages": [1],
                        "expected_observations": "",
                        "verification_status": "pending",
                    }
                ]
            }
        )
    )
    select_corpus(root, selection, output)
    assert other.read_bytes() == b"other"
