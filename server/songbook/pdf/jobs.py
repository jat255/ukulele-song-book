"""Persist frozen PDF requests and their immutable artifact metadata."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from ..storage.arrangements import ConflictError, LibraryStore, RecoveringError
from ..storage.db import connect


class QueueFull(Exception):
    """The bounded renderer queue has no free slot."""


class PdfJobs:
    def __init__(self, store: LibraryStore):
        self.store = store
        with connect(store.database) as db:
            db.executescript(
                (
                    Path(__file__).parents[1] / "storage/migrations/006_pdf_jobs.sql"
                ).read_text()
            )

    def enqueue(
        self, ident: str, revision: str, performance: dict, settings: dict
    ) -> dict:
        snapshot = self.store.get_arrangement(ident)
        if snapshot.revision != revision:
            raise ConflictError("Arrangement changed")
        frozen = {
            "arrangement_id": ident,
            "revision": revision,
            "source": snapshot.source,
            "source_refs": snapshot.source_refs,
            "performance": performance,
            "settings": settings,
        }
        diagnostics = []
        blocks = (snapshot.document or {}).get("blocks", [])
        if performance.get("semitones") and any(
            block.get("kind") == "tab" for block in blocks
        ):
            diagnostics.append("Tab remains unchanged by transposition.")
        if any(block.get("kind") == "unsupported" for block in blocks):
            diagnostics.append("Unsupported source content requires review.")
        return self._queue(ident, revision, frozen, diagnostics)

    def enqueue_setlist(
        self, setlists, ident: str, revision: str, settings: dict, song_break: str
    ) -> dict:
        from ..api.preferences import read as read_preferences

        # Hold the canonical-file lock and one SQLite write reservation while
        # collecting the set membership, source revisions and preferences.
        # Writers use the same lock or SQLite transaction, so the bundle has
        # one consistent point in time even when edits arrive concurrently.
        with self.store._lock(), connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision FROM setlists WHERE id=?", (ident,)
            ).fetchone()
            if not row:
                raise KeyError(ident)
            if row["revision"] != revision:
                raise ConflictError("Setlist changed")
            items = db.execute(
                "SELECT i.id,i.arrangement_id,COALESCE(m.deleted,0) AS deleted "
                "FROM setlist_items i LEFT JOIN library_metadata m ON m.arrangement_id=i.arrangement_id "
                "WHERE i.setlist_id=? ORDER BY i.position",
                (ident,),
            ).fetchall()
            if len(items) > 50:
                raise ValueError("Setlist PDF is limited to 50 occurrences")
            if not items or song_break not in {"new-page", "pack"}:
                raise ValueError("Invalid setlist PDF request")
            captured = {}
            for item in items:
                if item["deleted"]:
                    raise ConflictError("Setlist contains unavailable arrangements")
                arrangement_id = item["arrangement_id"]
                if arrangement_id not in captured:
                    try:
                        snapshot = self.store._read_locked(db, arrangement_id)
                    except (KeyError, RecoveringError):
                        raise ConflictError(
                            "Setlist contains unavailable arrangements"
                        ) from None
                    raw, _ = read_preferences(db, arrangement_id)
                    captured[arrangement_id] = (snapshot, json.loads(raw)["groups"])
        snapshots = []
        performances = []
        diagnostics = []
        frozen_arrangements = {}
        for occurrence in items:
            arrangement_id = occurrence["arrangement_id"]
            if arrangement_id in frozen_arrangements:
                frozen_snapshot, performance = frozen_arrangements[arrangement_id]
                snapshots.append({**frozen_snapshot, "occurrence_id": occurrence["id"]})
                performances.append(performance)
                continue
            snapshot, groups = captured[arrangement_id]
            performance = groups["performance"]["value"]
            if groups["performance"]["updated_at"] == 0:
                capo = next(
                    (
                        b.get("value")
                        for b in (snapshot.document or {}).get("blocks", [])
                        if b.get("kind") == "directive" and b.get("name") == "capo"
                    ),
                    None,
                )
                if capo and str(capo).isdigit() and 0 <= int(capo) <= 12:
                    performance["capo"] = int(capo)
            blocks = (snapshot.document or {}).get("blocks", [])
            if performance.get("semitones") and any(
                block.get("kind") == "tab" for block in blocks
            ):
                diagnostics.append("Tab remains unchanged by transposition.")
            if any(block.get("kind") == "unsupported" for block in blocks):
                diagnostics.append("Unsupported source content requires review.")
            frozen_snapshot = {
                "id": snapshot.id,
                "song_id": snapshot.song_id,
                "revision": snapshot.revision,
                "source": snapshot.source,
                "source_refs": snapshot.source_refs,
                "document": snapshot.document,
            }
            frozen_arrangements[snapshot.id] = (frozen_snapshot, performance)
            snapshots.append({**frozen_snapshot, "occurrence_id": occurrence["id"]})
            performances.append(performance)
        if sum(len(item["source"].encode("utf-8")) for item in snapshots) > 5_000_000:
            raise ValueError("Setlist exceeds source limit")
        frozen = {
            "setlist_id": ident,
            "revision": revision,
            "snapshots": snapshots,
            "performances": performances,
            "settings": settings,
            "song_break": song_break,
        }
        return self._queue(
            snapshots[0]["id"], revision, frozen, list(dict.fromkeys(diagnostics))
        )

    def _queue(
        self, ident: str, revision: str, frozen: dict, diagnostics: list[str]
    ) -> dict:
        payload = json.dumps(
            frozen, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        fingerprint = hashlib.sha256(payload.encode()).hexdigest()
        job_id = str(uuid.uuid4())
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            pending = db.execute(
                "SELECT count(*) FROM pdf_jobs WHERE state IN ('queued','processing')"
            ).fetchone()[0]
            if pending >= 10:
                raise QueueFull("PDF queue is full")
            db.execute(
                "INSERT INTO pdf_jobs(id,arrangement_id,source_revision,payload_json,fingerprint,state,diagnostics_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    job_id,
                    ident,
                    revision,
                    payload,
                    fingerprint,
                    "queued",
                    json.dumps(diagnostics),
                    time.time(),
                ),
            )
        return self.get(job_id)

    def get(self, ident: str) -> dict:
        with connect(self.store.database) as db:
            row = db.execute(
                "SELECT id,arrangement_id,source_revision,fingerprint,state,attempts,error_code,sha256,page_count,columns,diagnostics_json,renderer_json,created_at FROM pdf_jobs WHERE id=?",
                (ident,),
            ).fetchone()
        if not row:
            raise KeyError(ident)
        result = dict(row)
        result["diagnostics"] = json.loads(result.pop("diagnostics_json"))
        result["renderer"] = json.loads(result.pop("renderer_json"))
        result["retryable"] = result["error_code"] in {
            "render_failed",
            "render_timeout",
            "render_interrupted",
        }
        return result

    def run_one(self, worker_id: str) -> bool:
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            db.execute(
                "UPDATE pdf_jobs SET state='failed',error_code='render_interrupted' WHERE state='processing' AND lease_until<=? AND attempts>=3",
                (now,),
            )
            row = db.execute(
                "SELECT id,payload_json FROM pdf_jobs WHERE state='queued' OR (state='processing' AND lease_until<=? AND attempts<3) ORDER BY created_at LIMIT 1",
                (now,),
            ).fetchone()
            if not row:
                return False
            job_id = row["id"]
            payload = json.loads(row["payload_json"])
            db.execute(
                "UPDATE pdf_jobs SET state='processing',worker_id=?,lease_until=?,attempts=attempts+1 WHERE id=?",
                (worker_id, now + 150, job_id),
            )
        payload["output_dir"] = str(self.store.root / "pdfs" / job_id)
        environment = os.environ.copy()
        environment["SONGBOOK_RENDER_INHERIT_GROUP"] = "1"
        try:
            with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stdout:
                stdin.write(json.dumps(payload).encode())
                stdin.seek(0)
                process = subprocess.Popen(
                    [sys.executable, "-m", "server.songbook.pdf.render_subprocess"],
                    stdin=stdin,
                    stdout=stdout,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    env=environment,
                )
                try:
                    process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    raise TimeoutError("PDF rendering timed out") from None
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                if process.returncode != 0 or stdout.tell() > 1_000_000:
                    raise ValueError("PDF rendering failed")
                stdout.seek(0)
                result = json.load(stdout)
            if result.get("error_code") in {
                "tab_too_wide",
                "tab_too_tall",
                "content_too_wide",
                "render_failed",
            }:
                with connect(self.store.database) as db:
                    db.execute(
                        "UPDATE pdf_jobs SET state='failed',error_code=?,worker_id=NULL,lease_until=NULL WHERE id=? AND worker_id=?",
                        (result["error_code"], job_id, worker_id),
                    )
                return True
            path = Path(result["path"]).resolve()
            if (
                not path.is_relative_to((self.store.root / "pdfs" / job_id).resolve())
                or not path.is_file()
            ):
                raise ValueError("Invalid PDF artifact")
            if (
                path.stat().st_size > 100 * 1024 * 1024
                or not 1 <= result["page_count"] <= 500
            ):
                raise ValueError("PDF exceeds resource limit")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != result["sha256"] or path.name != digest + ".pdf":
                raise ValueError("PDF integrity mismatch")
            with connect(self.store.database) as db:
                db.execute(
                    "UPDATE pdf_jobs SET state='complete',sha256=?,page_count=?,columns=?,renderer_json=?,worker_id=NULL,lease_until=NULL WHERE id=? AND worker_id=? AND state='processing'",
                    (
                        digest,
                        result["page_count"],
                        result["columns"],
                        json.dumps(
                            {
                                "browser_version": result["browser_version"],
                                "font_hashes": result["font_hashes"],
                                "wraps": result["wraps"],
                            }
                        ),
                        job_id,
                        worker_id,
                    ),
                )
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            TimeoutError,
            subprocess.SubprocessError,
        ) as error:
            code = (
                "render_timeout" if isinstance(error, TimeoutError) else "render_failed"
            )
            with connect(self.store.database) as db:
                db.execute(
                    "UPDATE pdf_jobs SET state='failed',error_code=?,worker_id=NULL,lease_until=NULL WHERE id=? AND worker_id=?",
                    (code, job_id, worker_id),
                )
        return True

    def artifact(self, ident: str) -> tuple[dict, Path]:
        job = self.get(ident)
        if job["state"] != "complete" or not job["sha256"]:
            raise ValueError("PDF unavailable")
        path = (
            self.store.root / "pdfs" / job["id"] / (job["sha256"] + ".pdf")
        ).resolve()
        if (
            not path.is_relative_to(self.store.root / "pdfs" / job["id"])
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != job["sha256"]
        ):
            raise ValueError("PDF unavailable")
        return job, path
