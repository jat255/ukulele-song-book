"""Durable import queue and revision-checked review drafts."""

import base64
import hashlib
import json
import math
import sys
import time
import uuid
from difflib import SequenceMatcher
from pathlib import Path

from ..music_bridge import _run_bounded, parse_source
from ..storage.arrangements import ConflictError, LibraryStore
from ..storage.db import connect
from .failures import ConversionFailure, details


class FullPdfSelectionError(ValueError):
    """A safe, user-visible whole-document selection error."""


def revision(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


class ImportJobs:
    def __init__(self, store: LibraryStore):
        self.store = store
        with connect(store.database) as db:
            db.executescript(
                (
                    Path(__file__).parents[1] / "storage/migrations/003_imports.sql"
                ).read_text()
            )
            db.executescript(
                (
                    Path(__file__).parents[1]
                    / "storage/migrations/011_codex_activity.sql"
                ).read_text()
            )
            db.executescript(
                (
                    Path(__file__).parents[1]
                    / "storage/migrations/012_hidden_imports.sql"
                ).read_text()
            )

    def set_hidden(self, job_id: str, hidden: bool) -> None:
        """Change queue visibility without altering the import or its draft."""
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute(
                "SELECT 1 FROM import_jobs WHERE id=?", (job_id,)
            ).fetchone():
                raise KeyError(job_id)
            if hidden:
                db.execute(
                    "INSERT OR IGNORE INTO hidden_import_jobs(job_id) VALUES (?)",
                    (job_id,),
                )
            else:
                db.execute("DELETE FROM hidden_import_jobs WHERE job_id=?", (job_id,))

    def append_activity(self, job_id: str, worker_id: str, text: str) -> None:
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute(
                "SELECT 1 FROM import_jobs WHERE id=? AND worker_id=? AND state='processing'",
                (job_id, worker_id),
            ).fetchone():
                return
            db.execute(
                "INSERT INTO codex_job_activity(job_id,text) VALUES (?,substr(?,-1000000)) ON CONFLICT(job_id) DO UPDATE SET text=substr(text || excluded.text,-1000000)",
                (job_id, text),
            )

    def get_activity(self, job_id: str) -> dict:
        with connect(self.store.database) as db:
            if not db.execute(
                "SELECT 1 FROM import_jobs WHERE id=?", (job_id,)
            ).fetchone():
                raise KeyError(job_id)
            row = db.execute(
                "SELECT text FROM codex_job_activity WHERE job_id=?", (job_id,)
            ).fetchone()
            text = row["text"] if row else ""
            return {"text": text, "truncated": len(text) >= 1_000_000}

    def enqueue_import(
        self, source_id: str, selection: list[dict], method: str, idempotency_key: str
    ) -> dict:
        source_id = str(uuid.UUID(source_id))
        if (
            method not in ("direct", "local", "ai")
            or not idempotency_key
            or len(idempotency_key) > 200
        ):
            raise ValueError("Invalid import request")
        if any(part.get("all_pages") for part in selection):
            if (
                len(selection) != 1
                or selection[0].get("all_pages") is not True
                or selection[0].get("pages")
                or method not in ("local", "ai")
            ):
                raise FullPdfSelectionError(
                    "Entire PDF must be one song selection without explicit pages."
                )
            with connect(self.store.database) as db:
                source = db.execute(
                    "SELECT * FROM sources WHERE id=?", (source_id,)
                ).fetchone()
            if source is None or source["kind"] != "pdf":
                raise FullPdfSelectionError("Entire-document selection requires a PDF.")
            path = (self.store.root / source["path"]).resolve()
            if not path.is_relative_to(self.store.root / "sources" / source_id):
                raise FullPdfSelectionError("Source unavailable.")
            try:
                count = int(
                    _run_bounded(
                        [
                            sys.executable,
                            "-m",
                            "server.songbook.imports.count_subprocess",
                        ],
                        json.dumps({"path": str(path), "sha256": source["sha256"]}),
                        limit=100,
                        timeout=15,
                    )
                )
            except Exception as error:
                raise FullPdfSelectionError(
                    "Could not read the PDF page count. Check the original or choose custom pages."
                ) from error
            maximum = 5 if method == "ai" else 20
            if not 1 <= count <= maximum:
                raise FullPdfSelectionError(
                    f"Entire PDF has {count} pages; this conversion supports at most {maximum}. Choose custom pages; no pages were queued."
                )
            part = {
                key: value
                for key, value in selection[0].items()
                if key not in ("all_pages", "crop", "pages")
            }
            part["pages"] = list(range(1, count + 1))
            if selection[0].get("crop") is not None:
                part["rectangles"] = {
                    str(page): selection[0]["crop"] for page in part["pages"]
                }
            selection = [part]
        if method == "ai" and (
            len(selection) != 1
            or selection[0].get("authorization") is not True
            or not selection[0].get("provider")
            or not selection[0].get("model")
        ):
            raise ValueError("Explicit provider authorization required")
        if not selection or len(selection) > 20:
            raise ValueError("Invalid selection")
        for part in selection:
            pages = part.get("pages")
            if (
                not isinstance(pages, list)
                or len(pages) > 20
                or any(type(p) is not int or p < 1 or p > 500 for p in pages)
            ):
                raise ValueError("Invalid pages")
        if method == "direct" and (len(selection) != 1 or selection[0]["pages"]):
            raise ValueError("Direct imports require one source selection")
        if method != "direct" and any(not part["pages"] for part in selection):
            raise ValueError("Page selection required")
        for part in selection:
            rectangles = part.get("rectangles", {})
            if not isinstance(rectangles, dict):
                raise ValueError("Invalid crop")  # noqa: TRY004 - invalid request value
            for key, coords in rectangles.items():
                if (
                    not str(key).isdigit()
                    or int(key) not in part["pages"]
                    or not isinstance(coords, list)
                    or len(coords) != 4
                ):
                    raise ValueError("Invalid crop")
                if any(
                    type(value) not in (int, float) or not math.isfinite(value)
                    for value in coords
                ):
                    raise ValueError("Invalid crop")
                x0, y0, x1, y1 = coords
                if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                    raise ValueError("Invalid crop")
        if method == "ai" and (
            len(selection[0]["pages"]) > 5 or selection[0].get("rectangles")
        ):
            raise ValueError("AI requires at most five uncropped pages")
        if len({page for part in selection for page in part["pages"]}) > 20:
            raise ValueError("Selection exceeds page limit")
        for part in selection:
            if part.get("paired_source_id") is not None:
                if method != "direct" or len(selection) != 1:
                    raise ValueError("Invalid paired source")
                uuid.UUID(part["paired_source_id"])
                pages = part.get("paired_pages")
                if (
                    not isinstance(pages, list)
                    or not pages
                    or len(pages) > 20
                    or any(
                        type(page) is not int or page < 1 or page > 500
                        for page in pages
                    )
                ):
                    raise ValueError("Invalid paired pages")
        payload = json.dumps(selection, sort_keys=True, separators=(",", ":"))
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM import_jobs WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if row:
                if (
                    row["source_id"] != source_id
                    or row["selection_json"] != payload
                    or row["method"] != method
                ):
                    raise ConflictError("Idempotency key reused")
                ident = row["id"]
            else:
                if not db.execute(
                    "SELECT 1 FROM sources WHERE id=?", (source_id,)
                ).fetchone():
                    raise KeyError(source_id)
                for part in selection:
                    paired = part.get("paired_source_id")
                    if (
                        paired
                        and not db.execute(
                            "SELECT 1 FROM sources WHERE id=? AND kind='pdf'", (paired,)
                        ).fetchone()
                    ):
                        raise ValueError("Paired PDF unavailable")
                ident = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO import_jobs(id,source_id,selection_json,method,idempotency_key,state,created_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        ident,
                        source_id,
                        payload,
                        method,
                        idempotency_key,
                        "queued",
                        time.time(),
                    ),
                )
        return self.get_job(ident)

    def get_job(self, ident: str) -> dict:
        with connect(self.store.database) as db:
            row = db.execute(
                "SELECT * FROM import_jobs WHERE id=?", (ident,)
            ).fetchone()
            if row is None:
                raise KeyError(ident)
            result = dict(row)
            result["hidden"] = bool(
                db.execute(
                    "SELECT 1 FROM hidden_import_jobs WHERE job_id=?", (ident,)
                ).fetchone()
            )
            result["error_details"] = (
                details(result["error_code"]) if result["error_code"] else None
            )
            result["selection"] = json.loads(result.pop("selection_json"))
            activity = db.execute(
                "SELECT 1 FROM codex_job_activity WHERE job_id=?",
                (ident,),
            ).fetchone()
            result["activity_available"] = activity is not None
            result["drafts"] = []
            for raw in db.execute(
                "SELECT * FROM import_drafts WHERE job_id=? ORDER BY ordinal", (ident,)
            ):
                draft = dict(raw)
                draft["pages"] = json.loads(draft.pop("pages_json"))
                draft["diagnostics"] = json.loads(draft.pop("diagnostics_json"))
                provenance = db.execute(
                    "SELECT * FROM import_draft_provenance WHERE draft_id=?",
                    (draft["id"],),
                ).fetchone()
                draft["provider_metadata"] = (
                    json.loads(provenance["provider_json"]) if provenance else {}
                )
                draft["provenance"] = (
                    json.loads(provenance["provenance_json"]) if provenance else []
                )
                draft["uncertainties"] = (
                    json.loads(provenance["uncertainty_json"]) if provenance else []
                )
                result["drafts"].append(draft)
            return result

    def claim_job(
        self, worker_id: str, *, now: float | None = None, lease_seconds: int = 60
    ) -> dict | None:
        now = time.time() if now is None else now
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE import_jobs SET state='failed',error_code='retries_exhausted',worker_id=NULL WHERE state='processing' AND lease_until<=? AND (attempts>=3 OR method='ai')",
                (now,),
            )
            row = db.execute(
                "SELECT id FROM import_jobs WHERE state='queued' OR (state='processing' AND lease_until<=? AND attempts<3 AND method!='ai') ORDER BY created_at LIMIT 1",
                (now,),
            ).fetchone()
            if not row:
                return None
            ident = row["id"]
            db.execute(
                "UPDATE import_jobs SET state='processing',attempts=attempts+1,worker_id=?,lease_until=? WHERE id=?",
                (worker_id, now + lease_seconds, ident),
            )
        return self.get_job(ident)

    def renew_lease(
        self,
        job_id: str,
        worker_id: str,
        *,
        now: float | None = None,
        lease_seconds: int = 360,
    ) -> bool:
        now = time.time() if now is None else now
        with connect(self.store.database) as db:
            updated = db.execute(
                "UPDATE import_jobs SET lease_until=? WHERE id=? AND worker_id=? AND state='processing' AND lease_until>?",
                (now + lease_seconds, job_id, worker_id, now),
            )
            return bool(updated.rowcount)

    def discard_job(
        self, job_id: str, expected_state: str, expected_drafts: dict[str, str]
    ) -> None:
        """Remove pending drafts transactionally, retaining accepted history and originals."""
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute(
                "SELECT state FROM import_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if job is None:
                raise KeyError(job_id)
            drafts = db.execute(
                "SELECT id,revision,accepted_id,accepting_revision FROM import_drafts WHERE job_id=?",
                (job_id,),
            ).fetchall()
            pending = {
                row["id"]: row["revision"] for row in drafts if not row["accepted_id"]
            }
            if (
                job["state"] != expected_state
                or job["state"] in ("processing", "accepted")
                or pending != expected_drafts
                or any(
                    row["accepting_revision"] is not None and not row["accepted_id"]
                    for row in drafts
                )
            ):
                raise ConflictError("Import changed or is active")
            db.execute(
                "DELETE FROM import_draft_provenance WHERE draft_id IN (SELECT id FROM import_drafts WHERE job_id=? AND accepted_id IS NULL)",
                (job_id,),
            )
            db.execute(
                "DELETE FROM import_drafts WHERE job_id=? AND accepted_id IS NULL",
                (job_id,),
            )
            if any(row["accepted_id"] for row in drafts):
                db.execute(
                    "UPDATE import_jobs SET state='accepted',worker_id=NULL,lease_until=NULL WHERE id=?",
                    (job_id,),
                )
            else:
                db.execute("DELETE FROM import_jobs WHERE id=?", (job_id,))

    def retry_job(self, job_id: str, *, authorize_ai: bool = False) -> dict:
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state,attempts,method FROM import_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if not row:
                raise KeyError(job_id)
            if (
                row["state"] != "failed"
                or row["attempts"] >= 3
                or (row["method"] == "ai" and not authorize_ai)
            ):
                raise ValueError("Retry unavailable")
            db.execute(
                "UPDATE import_jobs SET state='queued',error_code=NULL WHERE id=?",
                (job_id,),
            )
        return self.get_job(job_id)

    def process_direct(self, job_id: str, worker_id: str) -> None:
        job = self.get_job(job_id)
        with connect(self.store.database) as db:
            source = db.execute(
                "SELECT * FROM sources WHERE id=?", (job["source_id"],)
            ).fetchone()
        if (
            source is None
            or source["kind"] not in ("cho", "chordpro")
            or job["method"] != "direct"
        ):
            raise ValueError("Direct import requires ChordPro")
        path = (self.store.root / source["path"]).resolve()
        if not path.is_relative_to(self.store.root / "sources" / source["id"]):
            raise ConversionFailure("source_unavailable")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ConversionFailure("source_unavailable")
        text = data.decode("utf-8")
        parse_source(text)
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state,worker_id FROM import_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if not row or row["state"] != "processing" or row["worker_id"] != worker_id:
                raise ConflictError("Lease lost")
            db.execute(
                "INSERT OR IGNORE INTO import_drafts VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    job_id,
                    0,
                    text,
                    revision(text),
                    "[]",
                    "[]",
                    None,
                    None,
                    None,
                ),
            )
            db.execute(
                "UPDATE import_jobs SET state='needs-review',worker_id=NULL,lease_until=NULL WHERE id=?",
                (job_id,),
            )

    def process_local(self, job_id: str, worker_id: str) -> None:
        job = self.get_job(job_id)
        with connect(self.store.database) as db:
            source = db.execute(
                "SELECT * FROM sources WHERE id=?", (job["source_id"],)
            ).fetchone()
        if source is None or source["kind"] != "pdf" or job["method"] != "local":
            raise ValueError("Local extraction requires PDF")
        path = (self.store.root / source["path"]).resolve()
        if (
            not path.is_relative_to(self.store.root / "sources" / source["id"])
            or not path.is_file()
        ):
            raise ConversionFailure("source_unavailable")
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ConversionFailure("source_unavailable")
        request = json.dumps(
            {
                "path": str(path),
                "sha256": source["sha256"],
                "selection": job["selection"],
            }
        )
        output = _run_bounded(
            [sys.executable, "-m", "server.songbook.imports.convert_subprocess"],
            request,
            limit=8_000_000,
            timeout=90,
        )
        drafts = json.loads(output)
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state,worker_id FROM import_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if not row or row["state"] != "processing" or row["worker_id"] != worker_id:
                raise ConflictError("Lease lost")
            for index, draft in enumerate(drafts):
                db.execute(
                    "INSERT OR IGNORE INTO import_drafts VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(uuid.uuid4()),
                        job_id,
                        index,
                        draft["source"],
                        revision(draft["source"]),
                        json.dumps(draft["pages"]),
                        json.dumps(draft["diagnostics"]),
                        None,
                        None,
                        None,
                    ),
                )
                saved_id = db.execute(
                    "SELECT id FROM import_drafts WHERE job_id=? AND ordinal=?",
                    (job_id, index),
                ).fetchone()[0]
                db.execute(
                    "INSERT OR REPLACE INTO import_draft_provenance VALUES (?,?,?,?)",
                    (
                        saved_id,
                        "{}",
                        json.dumps(draft["source_refs"]),
                        json.dumps(draft["uncertainty_spans"]),
                    ),
                )
            db.execute(
                "UPDATE import_jobs SET state='needs-review',worker_id=NULL,lease_until=NULL WHERE id=?",
                (job_id,),
            )

    def process_ai(self, job_id: str, worker_id: str, provider) -> None:
        from .ai import AIConversionService, ConversionAuthorization, PageSelection
        from .providers.base import SelectedPage

        job = self.get_job(job_id)
        selection = job["selection"][0]
        status = provider.status()
        if (
            not status.available
            or status.provider != selection["provider"]
            or status.model != selection["model"]
            or len(selection["pages"]) > status.page_limit
        ):
            raise ConversionFailure("provider_changed")
        with connect(self.store.database) as db:
            source = db.execute(
                "SELECT * FROM sources WHERE id=?", (job["source_id"],)
            ).fetchone()
        if not source or source["kind"] != "pdf":
            raise ValueError("Vision conversion requires PDF")
        path = (self.store.root / source["path"]).resolve()
        if (
            not path.is_relative_to(self.store.root / "sources" / source["id"])
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]
        ):
            raise ConversionFailure("source_unavailable")
        pages = []
        for page in selection["pages"]:
            output = _run_bounded(
                [sys.executable, "-m", "server.songbook.imports.render_subprocess"],
                json.dumps({"path": str(path), "page": page}),
                limit=16_000_000,
                timeout=30,
            )
            png = base64.b64decode(output, validate=True)
            pages.append(SelectedPage(page, png, hashlib.sha256(png).hexdigest()))
        service = AIConversionService(provider, self.store.database)
        authorization = ConversionAuthorization(
            source["id"],
            tuple(page.sha256 for page in pages),
            status.provider,
            status.model,
            True,
            nonce=f"{job_id}:{job['attempts']}",
            page_numbers=tuple(page.page for page in pages),
            source_hash=source["sha256"],
        )
        draft = service.convert(
            PageSelection(source["id"], pages, source["sha256"]), authorization
        )
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state,worker_id FROM import_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if not row or row["state"] != "processing" or row["worker_id"] != worker_id:
                raise ConflictError("Lease lost")
            db.execute(
                "INSERT OR IGNORE INTO import_drafts VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    job_id,
                    0,
                    draft.source,
                    revision(draft.source),
                    json.dumps(draft.pages),
                    json.dumps(draft.diagnostics),
                    None,
                    None,
                    None,
                ),
            )
            saved_id = db.execute(
                "SELECT id FROM import_drafts WHERE job_id=? AND ordinal=0", (job_id,)
            ).fetchone()[0]
            db.execute(
                "INSERT OR REPLACE INTO import_draft_provenance VALUES (?,?,?,?)",
                (
                    saved_id,
                    json.dumps(draft.provider_metadata),
                    json.dumps(draft.source_refs),
                    json.dumps(draft.uncertainty_spans),
                ),
            )
            db.execute(
                "UPDATE import_jobs SET state='needs-review',worker_id=NULL,lease_until=NULL WHERE id=?",
                (job_id,),
            )

    def suggest_duplicates(self, job_id: str, draft_id: str) -> list[dict]:
        job = self.get_job(job_id)
        draft = next((item for item in job["drafts"] if item["id"] == draft_id), None)
        if draft is None:
            raise KeyError(draft_id)
        title_values = (
            parse_source(draft["source"]).get("metadata", {}).get("title", [])
        )
        if not title_values:
            return []
        title = title_values[0].strip().casefold()
        if not title:
            return []
        candidates = []
        with connect(self.store.database) as db:
            rows = db.execute(
                "SELECT id,parsed_json FROM arrangements WHERE parsed_json IS NOT NULL LIMIT 5000"
            ).fetchall()
        for row in rows:
            values = json.loads(row["parsed_json"]).get("metadata", {}).get("title", [])
            if not values:
                continue
            score = SequenceMatcher(None, title, values[0].strip().casefold()).ratio()
            if score >= 0.75:
                candidates.append(
                    {"id": row["id"], "title": values[0], "score": round(score, 3)}
                )
        return sorted(
            candidates, key=lambda candidate: (-candidate["score"], candidate["title"])
        )[:10]

    def update_draft(
        self, job_id: str, draft_id: str, expected: str, source: str
    ) -> dict:
        parse_source(source)
        with connect(self.store.database) as db:
            cursor = db.execute(
                "UPDATE import_drafts SET source=?,revision=? WHERE id=? AND job_id=? AND revision=? AND accepted_id IS NULL AND accepting_revision IS NULL",
                (source, revision(source), draft_id, job_id, expected),
            )
            if not cursor.rowcount:
                raise ConflictError("Draft changed")
        return next(d for d in self.get_job(job_id)["drafts"] if d["id"] == draft_id)

    def accept_draft(
        self,
        job_id: str,
        draft_id: str,
        expected: str,
        song_id: str | None,
        *,
        acknowledge: bool = False,
    ):
        job = self.get_job(job_id)
        draft = next((d for d in job["drafts"] if d["id"] == draft_id), None)
        if draft is None:
            raise KeyError(draft_id)
        if draft["accepted_id"]:
            return self.store.get_arrangement(draft["accepted_id"])
        if draft["revision"] != expected:
            raise ConflictError("Draft changed")
        if (
            draft["diagnostics"]
            or job["selection"][draft["ordinal"]].get("paired_source_id")
        ) and not acknowledge:
            raise ValueError("Review acknowledgement required")
        if not draft["source"].strip():
            raise ValueError("Empty draft cannot be accepted as music")
        document = parse_source(draft["source"])
        if any(d.get("severity") == "error" for d in document.get("diagnostics", [])):
            raise ValueError("Draft has blocking errors")
        if not acknowledge and any(
            d.get("severity") == "warning" for d in document.get("diagnostics", [])
        ):
            raise ValueError("Review acknowledgement required")
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision,accepted_id,accepting_revision,accepting_song_id FROM import_drafts WHERE id=? AND job_id=?",
                (draft_id, job_id),
            ).fetchone()
            if not row or row["revision"] != expected:
                raise ConflictError("Draft changed")
            if row["accepted_id"]:
                return self.store.get_arrangement(row["accepted_id"])
            if row["accepting_revision"] is not None and (
                row["accepting_revision"] != expected
                or row["accepting_song_id"] != song_id
            ):
                raise ConflictError("Draft acceptance already in progress")
            db.execute(
                "UPDATE import_drafts SET accepting_revision=?, accepting_song_id=? WHERE id=?",
                (expected, song_id, draft_id),
            )
        refs = [{"source_id": job["source_id"], "pages": draft["pages"]}]
        selection = job["selection"][draft["ordinal"]]
        if selection.get("paired_source_id"):
            refs.append(
                {
                    "source_id": selection["paired_source_id"],
                    "pages": selection["paired_pages"],
                }
            )
        snapshot = self.store.create_arrangement(
            song_id,
            draft["source"],
            refs,
            "import-draft:" + draft_id,
        )
        with connect(self.store.database) as db:
            db.execute(
                "UPDATE import_drafts SET accepted_id=? WHERE id=?",
                (snapshot.id, draft_id),
            )
            if not db.execute(
                "SELECT 1 FROM import_drafts WHERE job_id=? AND accepted_id IS NULL",
                (job_id,),
            ).fetchone():
                db.execute(
                    "UPDATE import_jobs SET state='accepted' WHERE id=?", (job_id,)
                )
        return snapshot
