"""Inventory PDFs without changing the source directory."""

import fcntl
import hashlib
from pathlib import Path
from uuid import uuid4

import pdfplumber
from pdfminer.pdfparser import PDFSyntaxError
from pdfplumber.utils.exceptions import PdfminerException

from .manifest import BatchEntry, BatchManifest, load_manifest, save_manifest


def inventory(source_root: Path, output_root: Path) -> BatchManifest:
    source = source_root.resolve(strict=True)
    output = output_root.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Source and output directories must not overlap")
    if (output / "manifest.json").exists():
        raise FileExistsError("Batch already exists")
    entries = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part.startswith("._") or part == "__MACOSX" for part in relative.parts):
            continue
        if any(
            (source.joinpath(*relative.parts[:i])).is_symlink()
            for i in range(1, len(relative.parts) + 1)
        ):
            continue
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        ident = uuid4()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        error = None
        try:
            with pdfplumber.open(path) as pdf:
                page_count = len(pdf.pages)
        except (OSError, ValueError, PDFSyntaxError, PdfminerException) as exc:
            page_count = 0
            error = {"code": "pdf_probe_failed", "message": str(exc)}
        entries.append(
            BatchEntry(
                entry_id=ident,
                source_name=relative.as_posix(),
                source_sha256=digest,
                original_path=f"originals/{ident}.pdf",
                page_count=page_count,
                error=error,
            )
        )
    result = BatchManifest(batch_id=uuid4(), entries=entries)
    output.mkdir(parents=True, exist_ok=True)
    save_manifest(output / "manifest.json", result)
    return result


def select(
    output_root: Path, source_name: str, decision: str, reason: str | None = None
) -> None:
    with (output_root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = output_root / "manifest.json"
        manifest = load_manifest(path)
        entry = next(
            (item for item in manifest.entries if item.source_name == source_name), None
        )
        if entry is None:
            raise ValueError(f"Unknown source: {source_name}")
        if entry.state in ("running", "completed"):
            raise ValueError("Cannot change selection of a running or completed draft")
        if decision not in ("include", "exclude"):
            raise ValueError("Invalid decision")
        if decision == "exclude" and not reason:
            raise ValueError("An exclusion reason is required")
        entry.decision = decision
        entry.exclusion_reason = reason if decision == "exclude" else None
        save_manifest(path, manifest)
