"""Resumable conversion and portable batch export."""

import fcntl
import hashlib
import json
import subprocess
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import pdfplumber

from ..imports.pdf_extract import MAX_BYTES, MAX_PAGES, render_page
from ..pdf.models import PdfRenderRequest
from ..pdf.render import render_pdf
from ..storage.files import atomic_write
from .codex import convert_pdf
from .manifest import load_manifest, save_manifest


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def convert_batch(
    source_root: Path, output_root: Path, *, on_completed: Callable | None = None
):
    source_root = source_root.resolve(strict=True)
    output_root = output_root.resolve(strict=True)
    manifest_path = output_root / "manifest.json"
    with (output_root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_manifest(manifest_path)
        if any(entry.decision == "pending" for entry in manifest.entries):
            raise ValueError("Every PDF needs an explicit include or exclude decision")
        for entry in manifest.entries:
            if entry.decision != "include":
                continue
            source = (source_root / entry.source_name).resolve(strict=True)
            if (
                not source.is_relative_to(source_root)
                or digest(source) != entry.source_sha256
            ):
                raise ValueError(
                    f"Source changed: {entry.source_name}; create a new batch"
                )
            draft = output_root / "drafts" / f"{entry.entry_id}.cho"
            if entry.state == "completed":
                if not draft.is_file() or digest(draft) != entry.draft_sha256:
                    raise ValueError(f"Completed draft changed: {entry.source_name}")
                print(f"Skipping completed: {entry.source_name}", flush=True)
                continue
            if draft.exists():
                entry.state = "interrupted"
                entry.error = {
                    "code": "draft_conflict",
                    "message": "Existing draft preserved; resolve manually.",
                }
                save_manifest(manifest_path, manifest)
                continue
            entry.state = "running"
            print(
                f"Preparing: {entry.source_name} ({entry.page_count} pages)", flush=True
            )
            entry.error = None
            save_manifest(manifest_path, manifest)
            try:
                if (
                    source.stat().st_size > MAX_BYTES
                    or not 1 <= entry.page_count <= MAX_PAGES
                ):
                    raise ValueError("PDF exceeds size/page limit or could not be read")
                original = output_root / entry.original_path
                original.parent.mkdir(parents=True, exist_ok=True)
                if original.exists() and digest(original) != entry.source_sha256:
                    raise ValueError("Original copy conflicts with source")
                if not original.exists():
                    atomic_write(original, source.read_bytes())
                if digest(original) != entry.source_sha256:
                    raise ValueError("Source changed while copying")
                work = output_root / ".work" / str(entry.entry_id)
                work.mkdir(parents=True, exist_ok=True)
                images = []
                with pdfplumber.open(original) as pdf:
                    if len(pdf.pages) != entry.page_count:
                        raise ValueError("PDF page count changed")
                    text = "\n\n".join(
                        f"Page {n}:\n{page.extract_text() or ''}"
                        for n, page in enumerate(pdf.pages, 1)
                    )
                for number in range(1, entry.page_count + 1):
                    print(f"  Rendering page {number}/{entry.page_count}", flush=True)
                    image = work / f"page-{number}.png"
                    atomic_write(image, render_page(original, number, 120))
                    images.append(image.resolve())
                print("  Starting Codex conversion...", flush=True)
                result = convert_pdf(work.resolve(), images, text)
                draft.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(draft, result.source.encode("utf-8"))
                entry.draft_path = draft.relative_to(output_root).as_posix()
                entry.draft_sha256 = digest(draft)
                entry.diagnostics = [
                    "Compare the entire draft with the original PDF."
                ] + result.diagnostics
                entry.uncertainties = result.uncertainties
                entry.state = "completed"
                print(f"Completed: {entry.source_name}", flush=True)
            except KeyboardInterrupt:
                entry.state = "interrupted"
                entry.error = {
                    "code": "interrupted",
                    "message": "Conversion interrupted; retry to resume.",
                }
                save_manifest(manifest_path, manifest)
                raise
            except (
                OSError,
                ValueError,
                RuntimeError,
                TimeoutError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
            ) as exc:
                entry.state = "failed"
                entry.error = {"code": "conversion_failed", "message": str(exc)}
                save_manifest(manifest_path, manifest)
                if isinstance(
                    exc, (RuntimeError, TimeoutError, subprocess.TimeoutExpired)
                ):
                    break
            save_manifest(manifest_path, manifest)
            if entry.state == "completed" and on_completed is not None:
                on_completed(output_root, entry)
        return manifest


def render_preview(output_root: Path, entry) -> Path:
    """Render one completed draft using the songbook's PDF renderer."""
    if not entry.draft_path or not entry.draft_sha256:
        raise ValueError("Completed draft has no source or checksum")
    draft = output_root / entry.draft_path
    if not draft.is_file() or digest(draft) != entry.draft_sha256:
        raise ValueError(f"Draft missing or changed: {entry.source_name}")
    previews = output_root / "previews"
    previews.mkdir(parents=True, exist_ok=True)
    name = Path(entry.source_name).stem[:100]
    destination = previews / f"{name} - {entry.entry_id} - uniform.pdf"
    if destination.exists():
        return destination
    with tempfile.TemporaryDirectory(prefix="songbook-preview-") as directory:
        artifact = render_pdf(
            PdfRenderRequest(
                source=draft.read_text(encoding="utf-8"),
                output_dir=Path(directory),
                columns="auto",
                fit_lyric_lines=True,
            )
        )
        target = destination.open("xb")
        try:
            with target, artifact.path.open("rb") as source:
                import shutil

                shutil.copyfileobj(source, target)
        except OSError:
            destination.unlink(missing_ok=True)
            raise
    return destination


def render_previews(output_root: Path) -> list[Path]:
    """Render missing previews for completed entries without invoking Codex."""
    with (output_root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_manifest(output_root / "manifest.json")
        return [
            render_preview(output_root, entry)
            for entry in manifest.entries
            if entry.decision == "include" and entry.state == "completed"
        ]


def export_batch(output_root: Path, archive_path: Path) -> None:
    with (output_root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = load_manifest(output_root / "manifest.json")
        with (
            archive_path.open("xb") as stream,
            zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive,
        ):
            archive.writestr("manifest.json", manifest.model_dump_json(indent=2) + "\n")
            for entry in manifest.entries:
                if entry.decision == "include" and entry.state == "completed":
                    for relative in (entry.original_path, entry.draft_path):
                        if relative is None:
                            raise ValueError("Completed entry is missing an artifact")
                        archive.write(output_root / relative, relative)
