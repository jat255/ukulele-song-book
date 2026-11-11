"""Ordered setlists with stable per-occurrence identities."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from .arrangements import ConflictError, LibraryStore, RecoveringError
from .db import connect
from .library import LibraryIndex


class SetlistStore:
    def __init__(self, store: LibraryStore):
        self.store = store
        LibraryIndex(store)
        with connect(store.database) as db:
            db.executescript(
                (Path(__file__).parent / "migrations/007_setlists.sql").read_text()
            )

    def create(self, title: str) -> dict:
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("Invalid title")
        ident = str(uuid.uuid4())
        revision = str(uuid.uuid4())
        with connect(self.store.database) as db:
            db.execute("INSERT INTO setlists VALUES (?,?,?)", (ident, title, revision))
        return self.get(ident)

    def get(self, ident: str) -> dict:
        with connect(self.store.database) as db:
            row = db.execute("SELECT * FROM setlists WHERE id=?", (ident,)).fetchone()
            if not row:
                raise KeyError(ident)
            result = dict(row)
            rows = db.execute(
                "SELECT i.id,i.arrangement_id,a.parsed_json,COALESCE(m.deleted,0) AS deleted FROM setlist_items i JOIN arrangements a ON a.id=i.arrangement_id LEFT JOIN library_metadata m ON m.arrangement_id=a.id WHERE i.setlist_id=? ORDER BY i.position",
                (ident,),
            ).fetchall()
        result["items"] = []
        for item in rows:
            available = not bool(item["deleted"])
            if available:
                try:
                    self.store.get_arrangement(item["arrangement_id"])
                except (KeyError, RecoveringError):
                    available = False
            document = json.loads(item["parsed_json"]) if item["parsed_json"] else {}
            title = (document.get("metadata", {}).get("title") or ["Untitled"])[0]
            result["items"].append(
                {
                    "id": item["id"],
                    "arrangementId": item["arrangement_id"],
                    "available": available,
                    "title": title,
                }
            )
        return result

    def list(self) -> list[dict]:
        with connect(self.store.database) as db:
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM setlists ORDER BY title COLLATE NOCASE,id"
                )
            ]
        return [self.get(ident) for ident in ids]

    def save_setlist(
        self, ident: str, expected_revision: str, title: str, items: list[dict]
    ) -> dict:
        title = title.strip()
        if not title or len(title) > 200 or len(items) > 500:
            raise ValueError("Invalid setlist")
        normalized = []
        for item in items:
            normalized.append(
                (str(uuid.UUID(item["id"])), str(uuid.UUID(item["arrangementId"])))
            )
        if len({occurrence for occurrence, _ in normalized}) != len(normalized):
            raise ValueError("Duplicate occurrence ID")
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision FROM setlists WHERE id=?", (ident,)
            ).fetchone()
            if not row:
                raise KeyError(ident)
            if row["revision"] != expected_revision:
                raise ConflictError("Setlist changed")
            for occurrence_id, arrangement_id in normalized:
                owner = db.execute(
                    "SELECT setlist_id FROM setlist_items WHERE id=?", (occurrence_id,)
                ).fetchone()
                if owner and owner[0] != ident:
                    raise ValueError("Occurrence belongs to another setlist")
                if not db.execute(
                    "SELECT 1 FROM arrangements WHERE id=?", (arrangement_id,)
                ).fetchone():
                    raise ValueError("Arrangement not found")
            db.execute("DELETE FROM setlist_items WHERE setlist_id=?", (ident,))
            db.executemany(
                "INSERT INTO setlist_items VALUES (?,?,?,?)",
                [
                    (occurrence, ident, arrangement_id, index)
                    for index, (occurrence, arrangement_id) in enumerate(normalized)
                ],
            )
            db.execute(
                "UPDATE setlists SET title=?,revision=? WHERE id=?",
                (title, str(uuid.uuid4()), ident),
            )
        return self.get(ident)

    def delete(self, ident: str, expected_revision: str) -> None:
        with connect(self.store.database) as db:
            changed = db.execute(
                "DELETE FROM setlists WHERE id=? AND revision=?",
                (ident, expected_revision),
            )
            if not changed.rowcount:
                if not db.execute(
                    "SELECT 1 FROM setlists WHERE id=?", (ident,)
                ).fetchone():
                    raise KeyError(ident)
                raise ConflictError("Setlist changed")
