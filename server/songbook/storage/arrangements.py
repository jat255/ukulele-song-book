"""Managed sources and recoverable, revision-checked arrangements."""

import fcntl
import hashlib
import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from ..music_bridge import parse_source
from .db import connect, initialize
from .files import atomic_write


class ConflictError(Exception):
    """The supplied revision is stale."""


class RecoveringError(Exception):
    """An interrupted write requires recovery."""


@dataclass(frozen=True)
class SourceRecord:
    id: str
    sha256: str
    original_name: str
    kind: str
    path: Path


@dataclass(frozen=True)
class ArrangementSnapshot:
    id: str
    song_id: str
    revision: str
    source: str
    document: dict
    source_refs: list[dict]


class LibraryStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "library.sqlite"
        self.lock_path = self.root / ".library.lock"
        self.crash_hook = lambda stage: None
        initialize(self.database)

    @contextmanager
    def _lock(self):
        with self.lock_path.open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def canonical_path(self, ident: str) -> Path:
        uuid.UUID(ident)
        return self.root / "arrangements" / ident / "song.chordpro"

    def revision_path(self, ident: str, revision: str) -> Path:
        if len(revision) != 64 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("Invalid revision")
        return (
            self.canonical_path(ident).parent / "revisions" / (revision + ".chordpro")
        )

    def register_source(
        self, stream: BinaryIO, original_name: str, kind: str
    ) -> SourceRecord:
        if kind not in {"pdf", "cho", "chordpro"}:
            raise ValueError("Unsupported source type")
        chunks = []
        size = 0
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            if size > 100 * 1024 * 1024:
                raise ValueError("Source exceeds size limit")
            chunks.append(chunk)
        data = b"".join(chunks)
        digest = hashlib.sha256(data).hexdigest()
        with self._lock(), connect(self.database) as db:
            row = db.execute(
                "SELECT * FROM sources WHERE sha256=?", (digest,)
            ).fetchone()
            if row:
                existing = self.root / row["path"]
                if (
                    not existing.is_file()
                    or hashlib.sha256(existing.read_bytes()).hexdigest() != digest
                ):
                    raise RecoveringError("Retained original is unavailable or corrupt")
                return SourceRecord(
                    row["id"],
                    row["sha256"],
                    row["original_name"],
                    row["kind"],
                    self.root / row["path"],
                )
            ident = str(uuid.uuid4())
            relative = Path("sources") / ident / ("original." + kind)
            atomic_write(self.root / relative, data)
            name = Path(original_name.replace("\\", "/")).name
            db.execute(
                "INSERT INTO sources VALUES (?,?,?,?,?)",
                (ident, digest, name, kind, str(relative)),
            )
            return SourceRecord(ident, digest, name, kind, self.root / relative)

    def create_arrangement(
        self,
        song_id: str | None,
        source: str,
        refs: list[dict],
        acceptance_key: str | None,
    ) -> ArrangementSnapshot:
        document = parse_source(source)
        encoded = source.encode("utf-8")
        revision = hashlib.sha256(encoded).hexdigest()
        with self._lock():
            with connect(self.database) as db:
                if acceptance_key:
                    row = db.execute(
                        "SELECT arrangement_id FROM acceptances WHERE acceptance_key=?",
                        (acceptance_key,),
                    ).fetchone()
                    if row:
                        return self._read_locked(db, row["arrangement_id"])
                if song_id is None:
                    song_id = str(uuid.uuid4())
                    db.execute("INSERT INTO songs(id) VALUES (?)", (song_id,))
                else:
                    uuid.UUID(song_id)
                    if not db.execute(
                        "SELECT 1 FROM songs WHERE id=?", (song_id,)
                    ).fetchone():
                        raise KeyError(song_id)
                ident = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO arrangements(id,song_id) VALUES (?,?)",
                    (ident, song_id),
                )
                for ref in refs:
                    pages = ref.get("pages", [])
                    if not isinstance(pages, list) or any(
                        type(page) is not int or page < 1 for page in pages
                    ):
                        raise ValueError("Source pages must be one-based integers")
                    db.execute(
                        "INSERT INTO arrangement_sources VALUES (?,?,?,?)",
                        (
                            ident,
                            ref["source_id"],
                            json.dumps(ref.get("pages", [])),
                            ref.get("crop_asset_id"),
                        ),
                    )
                if acceptance_key:
                    db.execute(
                        "INSERT INTO acceptances VALUES (?,?)", (acceptance_key, ident)
                    )
                self.crash_hook("before_intent")
                db.execute(
                    "INSERT INTO write_intents VALUES (?,?,?,?)",
                    (ident, None, revision, json.dumps(document, ensure_ascii=False)),
                )
            self._apply_prepared(ident, revision, encoded)
            with connect(self.database) as db:
                return self._read_locked(db, ident)

    def save_arrangement(
        self, ident: str, expected_revision: str, source: str
    ) -> ArrangementSnapshot:
        document = parse_source(source)
        with self._lock():
            self._save_locked(ident, expected_revision, source, document)
            with connect(self.database) as db:
                return self._read_locked(db, ident)

    def _save_locked(
        self, ident: str, expected: str | None, source: str, document: dict
    ) -> None:
        encoded = source.encode("utf-8")
        revision = hashlib.sha256(encoded).hexdigest()
        parsed = json.dumps(document, ensure_ascii=False)
        with connect(self.database) as db:
            row = db.execute(
                "SELECT revision FROM arrangements WHERE id=?", (ident,)
            ).fetchone()
            if not row:
                raise KeyError(ident)
            if db.execute(
                "SELECT 1 FROM write_intents WHERE arrangement_id=?", (ident,)
            ).fetchone():
                raise RecoveringError(ident)
            if row["revision"] != expected:
                raise ConflictError("Revision conflict")
            self.crash_hook("before_intent")
            db.execute(
                "INSERT INTO write_intents VALUES (?,?,?,?)",
                (ident, expected, revision, parsed),
            )
        self._apply_prepared(ident, revision, encoded)

    def _apply_prepared(self, ident: str, revision: str, encoded: bytes) -> None:
        self.crash_hook("after_intent")
        atomic_write(self.revision_path(ident, revision), encoded)
        self.crash_hook("after_revision")
        atomic_write(self.canonical_path(ident), encoded)
        self.crash_hook("after_replace")
        self._finish_intent(ident)
        self.crash_hook("after_index")

    def _finish_intent(self, ident: str) -> None:
        with connect(self.database) as db:
            row = db.execute(
                "SELECT * FROM write_intents WHERE arrangement_id=?", (ident,)
            ).fetchone()
            if not row:
                return
            db.execute(
                "UPDATE arrangements SET revision=?,parsed_json=? WHERE id=?",
                (row["next_revision"], row["parsed_json"], ident),
            )
            db.execute(
                "INSERT OR IGNORE INTO arrangement_revisions VALUES (?,?)",
                (ident, row["next_revision"]),
            )
            db.execute(
                "INSERT INTO revision_events(arrangement_id,revision) VALUES (?,?)",
                (ident, row["next_revision"]),
            )
            db.execute(
                "DELETE FROM arrangement_search WHERE arrangement_id=?", (ident,)
            )
            doc = json.loads(row["parsed_json"])
            db.execute(
                "INSERT INTO arrangement_search VALUES (?,?)", (ident, doc["source"])
            )
            db.execute("DELETE FROM write_intents WHERE arrangement_id=?", (ident,))

    def _read_locked(self, db, ident: str) -> ArrangementSnapshot:
        row = db.execute("SELECT * FROM arrangements WHERE id=?", (ident,)).fetchone()
        if not row:
            raise KeyError(ident)
        if (
            not row["revision"]
            or db.execute(
                "SELECT 1 FROM write_intents WHERE arrangement_id=?", (ident,)
            ).fetchone()
        ):
            raise RecoveringError(ident)
        try:
            data = self.canonical_path(ident).read_bytes()
        except OSError as exc:
            raise RecoveringError(ident) from exc
        if hashlib.sha256(data).hexdigest() != row["revision"]:
            raise RecoveringError(ident)
        try:
            document = json.loads(row["parsed_json"])
            if document.get("schemaVersion") != 1 or document.get(
                "source"
            ) != data.decode("utf-8"):
                raise RecoveringError(ident)
        except (TypeError, ValueError, UnicodeDecodeError, AttributeError) as exc:
            raise RecoveringError(ident) from exc
        refs = [
            {
                "source_id": r["source_id"],
                "pages": json.loads(r["pages_json"]),
                "crop_asset_id": r["crop_asset_id"],
            }
            for r in db.execute(
                "SELECT * FROM arrangement_sources WHERE arrangement_id=?", (ident,)
            )
        ]
        return ArrangementSnapshot(
            ident,
            row["song_id"],
            row["revision"],
            data.decode("utf-8"),
            document,
            refs,
        )

    def get_arrangement(self, ident: str) -> ArrangementSnapshot:
        with self._lock(), connect(self.database) as db:
            return self._read_locked(db, ident)

    def indexed_revision(self, ident: str) -> str:
        with self._lock(), connect(self.database) as db:
            row = db.execute(
                "SELECT revision FROM arrangements WHERE id=?", (ident,)
            ).fetchone()
            if not row:
                raise KeyError(ident)
            return row["revision"]

    def restore_revision(
        self, ident: str, expected_revision: str, target_revision: str
    ) -> ArrangementSnapshot:
        with self._lock():
            with connect(self.database) as db:
                if not db.execute(
                    "SELECT 1 FROM arrangement_revisions WHERE arrangement_id=? AND revision=?",
                    (ident, target_revision),
                ).fetchone():
                    raise KeyError(target_revision)
            source = (
                self.revision_path(ident, target_revision).read_bytes().decode("utf-8")
            )
            self._save_locked(ident, expected_revision, source, parse_source(source))
            with connect(self.database) as db:
                return self._read_locked(db, ident)

    def recover_pending_writes(self) -> dict:
        recovered = 0
        with self._lock():
            with connect(self.database) as db:
                rows = db.execute("SELECT * FROM write_intents").fetchall()
            for row in rows:
                ident = row["arrangement_id"]
                target = row["next_revision"]
                path = self.revision_path(ident, target)
                try:
                    pending_document = json.loads(row["parsed_json"])
                    pending_source = pending_document["source"].encode("utf-8")
                    if (
                        pending_document.get("schemaVersion") != 1
                        or hashlib.sha256(pending_source).hexdigest() != target
                    ):
                        raise RecoveringError(ident)
                except (KeyError, TypeError, ValueError, AttributeError) as exc:
                    raise RecoveringError(ident) from exc
                if (
                    path.exists()
                    and hashlib.sha256(path.read_bytes()).hexdigest() == target
                ):
                    atomic_write(self.canonical_path(ident), path.read_bytes())
                    self._finish_intent(ident)
                    recovered += 1
                elif row["previous_revision"]:
                    previous = self.revision_path(ident, row["previous_revision"])
                    data = previous.read_bytes()
                    if hashlib.sha256(data).hexdigest() != row["previous_revision"]:
                        raise RecoveringError(ident)
                    atomic_write(self.canonical_path(ident), data)
                    with connect(self.database) as db:
                        db.execute(
                            "DELETE FROM write_intents WHERE arrangement_id=?", (ident,)
                        )
                    recovered += 1
                else:
                    try:
                        data = json.loads(row["parsed_json"])["source"].encode("utf-8")
                    except (KeyError, TypeError, ValueError) as exc:
                        raise RecoveringError(ident) from exc
                    if hashlib.sha256(data).hexdigest() != target:
                        raise RecoveringError(ident)
                    atomic_write(path, data)
                    atomic_write(self.canonical_path(ident), data)
                    self._finish_intent(ident)
                    recovered += 1
            with connect(self.database) as db:
                accepted = db.execute(
                    "SELECT id,revision,parsed_json FROM arrangements WHERE revision IS NOT NULL"
                ).fetchall()
            for row in accepted:
                ident = row["id"]
                canonical = self.canonical_path(ident)
                if (
                    not canonical.exists()
                    or hashlib.sha256(canonical.read_bytes()).hexdigest()
                    != row["revision"]
                ):
                    revision_file = self.revision_path(ident, row["revision"])
                    if (
                        not revision_file.exists()
                        or hashlib.sha256(revision_file.read_bytes()).hexdigest()
                        != row["revision"]
                    ):
                        raise RecoveringError(ident)
                    atomic_write(canonical, revision_file.read_bytes())
                    recovered += 1
                source = canonical.read_bytes().decode("utf-8")
                with connect(self.database) as db:
                    indexed = db.execute(
                        "SELECT content FROM arrangement_search WHERE arrangement_id=?",
                        (ident,),
                    ).fetchall()
                    try:
                        document = json.loads(row["parsed_json"])
                        valid = (
                            document.get("schemaVersion") == 1
                            and document.get("source") == source
                        )
                    except (ValueError, TypeError, AttributeError):
                        valid = False
                    if (
                        not valid
                        or len(indexed) != 1
                        or indexed[0]["content"] != source
                    ):
                        document = parse_source(source)
                        db.execute(
                            "UPDATE arrangements SET parsed_json=? WHERE id=?",
                            (json.dumps(document, ensure_ascii=False), ident),
                        )
                        db.execute(
                            "DELETE FROM arrangement_search WHERE arrangement_id=?",
                            (ident,),
                        )
                        db.execute(
                            "INSERT INTO arrangement_search VALUES (?,?)",
                            (ident, source),
                        )
                        recovered += 1
        return {"recovered": recovered}
