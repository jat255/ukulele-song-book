"""Searchable, separately revisioned library metadata."""

import json
import re
import time
from pathlib import Path

from .arrangements import ConflictError, LibraryStore
from .db import connect


class LibraryIndex:
    def __init__(self, store: LibraryStore):
        self.store = store
        with connect(store.database) as db:
            db.executescript(
                (
                    Path(__file__).parent / "migrations/004_library_metadata.sql"
                ).read_text()
            )

    def metadata(self, ident: str) -> dict:
        with connect(self.store.database) as db:
            if not db.execute(
                "SELECT 1 FROM arrangements WHERE id=?", (ident,)
            ).fetchone():
                raise KeyError(ident)
            db.execute(
                "INSERT OR IGNORE INTO library_metadata(arrangement_id) VALUES (?)",
                (ident,),
            )
            row = dict(
                db.execute(
                    "SELECT * FROM library_metadata WHERE arrangement_id=?", (ident,)
                ).fetchone()
            )
            row["favorite"] = bool(row["favorite"])
            row["deleted"] = bool(row["deleted"])
            row["tags"] = [
                item[0]
                for item in db.execute(
                    "SELECT tag FROM library_tags WHERE arrangement_id=? ORDER BY tag",
                    (ident,),
                )
            ]
            return row

    def update_metadata(
        self, ident: str, expected: int, *, favorite: bool, tags: list[str], notes: str
    ) -> dict:
        if (
            len(tags) > 100
            or any(
                not isinstance(tag, str) or not tag.strip() or len(tag) > 100
                for tag in tags
            )
            or len(notes) > 100_000
        ):
            raise ValueError("Invalid metadata")
        self.metadata(ident)
        with connect(self.store.database) as db:
            db.execute("BEGIN IMMEDIATE")
            updated = db.execute(
                "UPDATE library_metadata SET favorite=?,notes=?,revision=revision+1 WHERE arrangement_id=? AND revision=? AND deleted=0",
                (favorite, notes, ident, expected),
            )
            if not updated.rowcount:
                raise ConflictError("Metadata changed")
            db.execute("DELETE FROM library_tags WHERE arrangement_id=?", (ident,))
            db.executemany(
                "INSERT INTO library_tags VALUES (?,?)",
                [(ident, tag) for tag in sorted({tag.strip() for tag in tags})],
            )
        return self.metadata(ident)

    def delete(self, ident: str, expected: int) -> None:
        self.metadata(ident)
        with connect(self.store.database) as db:
            changed = db.execute(
                "UPDATE library_metadata SET deleted=1,revision=revision+1 WHERE arrangement_id=? AND revision=? AND deleted=0",
                (ident, expected),
            )
            if not changed.rowcount:
                raise ConflictError("Metadata changed")

    def mark_played(self, ident: str) -> None:
        metadata = self.metadata(ident)
        if metadata["deleted"]:
            raise KeyError(ident)
        with connect(self.store.database) as db:
            db.execute(
                "UPDATE library_metadata SET last_played=?,revision=revision+1 WHERE arrangement_id=? AND deleted=0",
                (time.time(), ident),
            )

    def search_library(
        self, query: str, tags: list[str], favorites_only: bool, *, recent: bool = False
    ) -> list[dict]:
        if len(query) > 500 or len(tags) > 100:
            raise ValueError("Search exceeds limits")
        words = re.findall(r"\w+", query, re.UNICODE)
        if query.strip() and not words:
            return []
        with connect(self.store.database) as db:
            if len(words) > 25:
                raise ValueError("Search exceeds term limit")
            if words:
                matches = None
                tag_rows = db.execute(
                    "SELECT arrangement_id,tag FROM library_tags"
                ).fetchall()
                for word in words:
                    expression = '"' + word.replace('"', '""') + '"'
                    current = {
                        row[0]
                        for row in db.execute(
                            "SELECT arrangement_id FROM arrangement_search WHERE arrangement_search MATCH ?",
                            (expression,),
                        )
                    }
                    current.update(
                        row["arrangement_id"]
                        for row in tag_rows
                        if word.casefold() in row["tag"].casefold()
                    )
                    matches = current if matches is None else matches & current
                rows = [
                    row
                    for row in db.execute(
                        "SELECT * FROM arrangements WHERE revision IS NOT NULL"
                    )
                    if row["id"] in matches
                ]
            else:
                rows = db.execute(
                    "SELECT * FROM arrangements WHERE revision IS NOT NULL"
                ).fetchall()
        items = []
        for row in rows:
            metadata = self.metadata(row["id"])
            if (
                metadata["deleted"]
                or (recent and metadata["last_played"] is None)
                or (favorites_only and not metadata["favorite"])
                or not set(tags).issubset(metadata["tags"])
            ):
                continue
            document = json.loads(row["parsed_json"])
            fields = document.get("metadata", {})
            items.append(
                {
                    **metadata,
                    "source_only": False,
                    "metadata_revision": metadata["revision"],
                    "id": row["id"],
                    "song_id": row["song_id"],
                    "revision": row["revision"],
                    "title": (fields.get("title") or ["Untitled"])[0],
                    "artist": (fields.get("artist") or [""])[0],
                }
            )
        if not favorites_only and not tags and not recent:
            with connect(self.store.database) as db:
                sources = db.execute(
                    "SELECT s.id,s.original_name FROM sources s WHERE NOT EXISTS (SELECT 1 FROM arrangement_sources r WHERE r.source_id=s.id)"
                ).fetchall()
            for source in sources:
                if all(
                    word.casefold() in source["original_name"].casefold()
                    for word in words
                ):
                    items.append(
                        {
                            "id": source["id"],
                            "source_only": True,
                            "title": source["original_name"],
                            "artist": "",
                            "favorite": False,
                            "tags": [],
                            "notes": "",
                            "last_played": None,
                        }
                    )
        if recent:
            return sorted(items, key=lambda item: (-item["last_played"], item["id"]))
        return sorted(items, key=lambda item: (item["title"].casefold(), item["id"]))
