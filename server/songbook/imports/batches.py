"""Validate and stage portable batches as reviewed import drafts."""

import hashlib
import io
import json
import stat
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from pypdf import PdfReader

from ..bulk.manifest import BatchManifest
from ..storage.arrangements import LibraryStore
from ..storage.db import connect
from .jobs import ImportJobs, revision

MAX_ARCHIVE = 1024 * 1024 * 1024


def import_archive(path: Path, store: LibraryStore) -> dict:
    if path.stat().st_size > MAX_ARCHIVE:
        raise ValueError("Batch exceeds size limit")
    if not zipfile.is_zipfile(path):
        raise ValueError("Invalid ZIP archive")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if (
            len(infos) > 30001
            or len(names) != len(set(names))
            or sum(info.file_size for info in infos) > MAX_ARCHIVE
        ):
            raise ValueError("Batch has too many entries or is too large")
        for info in infos:
            name = info.filename
            p = PurePosixPath(name)
            if (
                p.is_absolute()
                or ".." in p.parts
                or "\\" in name
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
                raise ValueError("Unsafe archive path")
        if (
            "manifest.json" not in names
            or archive.getinfo("manifest.json").file_size > 10_000_000
        ):
            raise ValueError("Missing or oversized manifest")
        manifest = BatchManifest.model_validate_json(archive.read("manifest.json"))
        if len(manifest.entries) > 10000:
            raise ValueError("Too many batch entries")
        ready = []
        skipped = []
        used_artifacts = set()
        for entry in manifest.entries:
            if entry.decision != "include" or entry.state != "completed":
                skipped.append({"entry_id": str(entry.entry_id), "reason": entry.state})
                continue
            if (
                not entry.draft_path
                or not entry.draft_sha256
                or entry.original_path not in names
                or entry.draft_path not in names
            ):
                raise ValueError("Missing completed entry artifact")
            if (
                entry.original_path == entry.draft_path
                or entry.original_path in used_artifacts
                or entry.draft_path in used_artifacts
            ):
                raise ValueError("Batch artifact path reused")
            used_artifacts.update((entry.original_path, entry.draft_path))
            if (
                archive.getinfo(entry.original_path).file_size > 100 * 1024 * 1024
                or archive.getinfo(entry.draft_path).file_size > 4_000_000
            ):
                raise ValueError("Entry exceeds size limit")
            pdf = archive.read(entry.original_path)
            raw = archive.read(entry.draft_path)
            if (
                hashlib.sha256(pdf).hexdigest() != entry.source_sha256
                or hashlib.sha256(raw).hexdigest() != entry.draft_sha256
            ):
                raise ValueError("Artifact hash mismatch")
            try:
                source = raw.decode("utf-8")
                pages = len(PdfReader(io.BytesIO(pdf)).pages)
            except Exception as exc:
                raise ValueError("Invalid PDF or draft") from exc
            if (
                not source.strip()
                or len(source) > 1_000_000
                or pages != entry.page_count
                or not 1 <= pages <= 500
            ):
                raise ValueError("Invalid draft or PDF page count")
            for span in entry.uncertainties:
                if (
                    not isinstance(span, dict)
                    or not isinstance(span.get("start"), int)
                    or not isinstance(span.get("end"), int)
                    or not isinstance(span.get("reason"), str)
                    or not 0 <= span["start"] <= span["end"] <= len(source)
                ):
                    raise ValueError("Invalid uncertainty range")
            ready.append((entry, pdf, raw, source))
    ImportJobs(store)
    with connect(store.database) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS bulk_import_identity (source_sha256 TEXT NOT NULL, draft_sha256 TEXT NOT NULL, job_id TEXT NOT NULL, PRIMARY KEY(source_sha256,draft_sha256))"
        )
    imported, existing = [], []
    for entry, pdf, raw, source in ready:
        original = store.register_source(
            io.BytesIO(pdf), Path(entry.source_name).name, "pdf"
        )
        chordpro = store.register_source(
            io.BytesIO(raw), Path(entry.source_name).stem + ".cho", "cho"
        )
        with connect(store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT job_id FROM bulk_import_identity WHERE source_sha256=? AND draft_sha256=?",
                (entry.source_sha256, entry.draft_sha256),
            ).fetchone()
            if row:
                if db.execute(
                    "SELECT 1 FROM import_jobs WHERE id=?", (row["job_id"],)
                ).fetchone():
                    existing.append(
                        {"entry_id": str(entry.entry_id), "job_id": row["job_id"]}
                    )
                else:
                    skipped.append(
                        {"entry_id": str(entry.entry_id), "reason": "already-discarded"}
                    )
                continue
            job_id, draft_id = str(uuid.uuid4()), str(uuid.uuid4())
            selection = [
                {
                    "pages": [],
                    "paired_source_id": original.id,
                    "paired_pages": list(range(1, entry.page_count + 1)),
                }
            ]
            db.execute(
                "INSERT INTO import_jobs(id,source_id,selection_json,method,idempotency_key,state,created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    job_id,
                    chordpro.id,
                    json.dumps(selection),
                    "direct",
                    "batch:" + job_id,
                    "needs-review",
                    time.time(),
                ),
            )
            db.execute(
                "INSERT INTO import_drafts(id,job_id,ordinal,source,revision,pages_json,diagnostics_json) VALUES (?,?,?,?,?,?,?)",
                (
                    draft_id,
                    job_id,
                    0,
                    source,
                    revision(source),
                    "[]",
                    json.dumps(
                        [
                            "Compare the entire draft with the original PDF.",
                            *entry.diagnostics,
                        ]
                    ),
                ),
            )
            db.execute(
                "INSERT INTO import_draft_provenance(draft_id,provider_json,provenance_json,uncertainty_json) VALUES (?,?,?,?)",
                (
                    draft_id,
                    json.dumps({"provider": "codex"}),
                    "[]",
                    json.dumps(entry.uncertainties),
                ),
            )
            db.execute(
                "INSERT INTO bulk_import_identity VALUES (?,?,?)",
                (entry.source_sha256, entry.draft_sha256, job_id),
            )
            imported.append({"entry_id": str(entry.entry_id), "job_id": job_id})
    return {
        "batch_id": str(manifest.batch_id),
        "imported": imported,
        "existing": existing,
        "skipped": skipped,
    }
