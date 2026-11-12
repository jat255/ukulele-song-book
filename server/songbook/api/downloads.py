"""Authenticated immutable manifests for explicitly requested downloads."""

import hashlib
import json
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ..storage.arrangements import RecoveringError
from ..storage.db import connect
from .auth import Principal, require_session

router = APIRouter(prefix="/api/downloads")
session = Depends(require_session)


def initialize(store):
    with connect(store.database) as db:
        db.executescript(
            (
                Path(__file__).parents[1]
                / "storage/migrations/008_library_identity.sql"
            ).read_text()
        )
        db.execute(
            "INSERT OR IGNORE INTO library_identity VALUES (1,?)", (str(uuid.uuid4()),)
        )


def manifest(request, selection_id, arrangement_ids, playlist=None):
    store = request.app.state.store
    snapshots = []
    assets = {}
    with store._lock(), connect(store.database) as db:
        db.execute("BEGIN")
        library_id = db.execute("SELECT id FROM library_identity").fetchone()[0]
        if playlist is not None:
            row = db.execute(
                "SELECT id,title,revision FROM setlists WHERE id=?", (playlist["id"],)
            ).fetchone()
            if not row:
                raise HTTPException(404, detail="Setlist not found")
            items = db.execute(
                "SELECT i.id,i.arrangement_id,a.parsed_json,COALESCE(m.deleted,0) AS deleted FROM setlist_items i JOIN arrangements a ON a.id=i.arrangement_id LEFT JOIN library_metadata m ON m.arrangement_id=a.id WHERE i.setlist_id=? ORDER BY i.position",
                (playlist["id"],),
            ).fetchall()
            playlist = dict(row)
            playlist["items"] = [
                {
                    "id": item["id"],
                    "arrangementId": item["arrangement_id"],
                    "available": not bool(item["deleted"]),
                    "title": (
                        json.loads(item["parsed_json"]).get("metadata", {}).get("title")
                        or ["Untitled"]
                    )[0],
                }
                for item in items
            ]
            if any(not item["available"] for item in playlist["items"]):
                raise HTTPException(
                    409, detail="Selection contains an unavailable arrangement"
                )
            arrangement_ids = [item["arrangementId"] for item in playlist["items"]]
        for ident in dict.fromkeys(arrangement_ids):
            deleted = db.execute(
                "SELECT deleted FROM library_metadata WHERE arrangement_id=?", (ident,)
            ).fetchone()
            if deleted and deleted[0]:
                raise HTTPException(
                    409, detail="Selection contains an unavailable arrangement"
                )
            try:
                snapshot = store._read_locked(db, ident)
            except (KeyError, RecoveringError):
                raise HTTPException(
                    409, detail="Selection contains an unavailable arrangement"
                ) from None
            snapshots.append(
                {
                    **asdict(snapshot),
                    "sha256": snapshot.revision,
                    "size": len(snapshot.source.encode("utf-8")),
                    "mime": "text/plain; charset=utf-8",
                }
            )
            for ref in snapshot.source_refs:
                if ref.get("crop_asset_id"):
                    asset = db.execute(
                        "SELECT id,sha256,path FROM assets WHERE id=?",
                        (ref["crop_asset_id"],),
                    ).fetchone()
                    if not asset:
                        raise HTTPException(
                            409, detail="Required crop asset unavailable"
                        )
                    path = (store.root / asset["path"]).resolve()
                    if (
                        not path.is_relative_to(store.root / "assets")
                        or not path.is_file()
                    ):
                        raise HTTPException(
                            409, detail="Required crop asset unavailable"
                        )
                    data = path.read_bytes()
                    if hashlib.sha256(data).hexdigest() != asset["sha256"]:
                        raise HTTPException(409, detail="Required crop asset corrupted")
                    assets[asset["id"]] = {
                        "id": asset["id"],
                        "url": f"/api/downloads/assets/{asset['id']}",
                        "sha256": asset["sha256"],
                        "size": len(data),
                        "mime": "application/octet-stream",
                        "optional": False,
                        "available": True,
                    }
                source = db.execute(
                    "SELECT id,sha256,path,kind FROM sources WHERE id=?",
                    (ref["source_id"],),
                ).fetchone()
                if source:
                    path = (store.root / source["path"]).resolve()
                    available = False
                    size = None
                    if path.is_relative_to(store.root / "sources" / source["id"]):
                        try:
                            digest = hashlib.sha256()
                            size = 0
                            with path.open("rb") as original:
                                while chunk := original.read(1024 * 1024):
                                    digest.update(chunk)
                                    size += len(chunk)
                            available = digest.hexdigest() == source["sha256"]
                        except OSError:
                            pass
                    assets[source["id"]] = {
                        "id": source["id"],
                        "url": f"/api/sources/{source['id']}/original",
                        "sha256": source["sha256"],
                        "size": size,
                        "available": available,
                        "mime": "application/pdf"
                        if source["kind"] == "pdf"
                        else "text/plain",
                        "optional": True,
                    }
    return {
        "schemaVersion": 1,
        "libraryId": library_id,
        "principalId": "owner",
        "selectionId": selection_id,
        "snapshots": snapshots,
        "assets": list(assets.values()),
        "setlist": playlist,
    }


@router.get("/arrangements/{ident}")
def arrangement(ident: str, request: Request, principal: Principal = session):
    return manifest(request, f"arrangement:{ident}", [ident])


@router.get("/setlists/{ident}")
def setlist(ident: str, request: Request, principal: Principal = session):
    try:
        playlist = request.app.state.setlists.get(ident)
    except KeyError:
        raise HTTPException(404, detail="Setlist not found") from None
    if any(not item["available"] for item in playlist["items"]):
        raise HTTPException(409, detail="Selection contains an unavailable arrangement")
    return manifest(
        request,
        f"setlist:{ident}",
        [item["arrangementId"] for item in playlist["items"]],
        playlist,
    )


@router.get("/assets/{ident}")
def asset(ident: str, request: Request, principal: Principal = session):
    try:
        ident = str(uuid.UUID(ident))
    except ValueError:
        raise HTTPException(404, detail="Asset not found") from None
    store = request.app.state.store
    with connect(store.database) as db:
        row = db.execute(
            "SELECT path,sha256 FROM assets WHERE id=?", (ident,)
        ).fetchone()
    if not row:
        raise HTTPException(404, detail="Asset not found")
    path = (store.root / row["path"]).resolve()
    if (
        not path.is_relative_to(store.root / "assets")
        or not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]
    ):
        raise HTTPException(404, detail="Asset unavailable")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/identity")
def identity(request: Request, principal: Principal = session):
    with connect(request.app.state.store.database) as db:
        ident = db.execute("SELECT id FROM library_identity").fetchone()[0]
    return {"libraryId": ident, "principalId": "owner"}
