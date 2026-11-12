"""Authenticated, bounded, private portable export jobs."""

import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..portability.export import export_arrangement, export_library
from .auth import Principal, require_csrf, require_session

router = APIRouter(prefix="/api/exports")
session = Depends(require_session)


class ExportRequest(BaseModel):
    kind: Literal["library", "chordpro", "arrangement"]
    arrangement_id: str | None = None


class ExportStatus(BaseModel):
    id: str
    state: Literal["pending", "complete", "failed"]


class ExportJobs:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self.jobs = {}
        self.directory = None

    def create(self, body: ExportRequest, owner: str) -> dict:
        if body.kind != "library":
            if not body.arrangement_id:
                raise ValueError("Arrangement required")
            self.store.get_arrangement(str(uuid.UUID(body.arrangement_id)))
        elif body.arrangement_id:
            raise ValueError("Unexpected arrangement")
        with self.lock:
            now = time.monotonic()
            for ident, job in list(self.jobs.items()):
                if job["state"] != "pending" and now - job["created"] > 3600:
                    job["path"].unlink(missing_ok=True)
                    del self.jobs[ident]
            if any(job["state"] == "pending" for job in self.jobs.values()):
                raise OverflowError("Export queue full")
            if len(self.jobs) >= 5:
                oldest = min(self.jobs, key=lambda item: self.jobs[item]["created"])
                self.jobs[oldest]["path"].unlink(missing_ok=True)
                del self.jobs[oldest]
            if self.directory is None:
                self.directory = tempfile.TemporaryDirectory(
                    prefix="songbook-private-exports-"
                )
            ident = str(uuid.uuid4())
            path = Path(self.directory.name) / ident
            self.jobs[ident] = {
                "id": ident,
                "state": "pending",
                "path": path,
                "owner": owner,
                "kind": body.kind,
                "created": now,
            }

        def run():
            try:
                if body.kind == "library":
                    export_library(self.store, path)
                else:
                    export_arrangement(
                        self.store,
                        body.arrangement_id,
                        path,
                        body.kind == "arrangement",
                    )
                state = "complete"
            except Exception:  # noqa: BLE001 - no private details in logs or status
                path.unlink(missing_ok=True)
                state = "failed"
            with self.lock:
                self.jobs[ident]["state"] = state

        threading.Thread(target=run, daemon=True).start()
        return {"id": ident, "state": "pending"}

    def get(self, ident: str, owner: str) -> dict:
        with self.lock:
            job = self.jobs.get(ident)
            if (
                not job
                or job["owner"] != owner
                or time.monotonic() - job["created"] > 3600
            ):
                raise KeyError(ident)
            return dict(job)


@router.post("", status_code=202, response_model=ExportStatus)
def create(body: ExportRequest, request: Request, principal: Principal = session):
    require_csrf(request, principal)
    try:
        return request.app.state.export_jobs.create(body, principal.session_hash)
    except (KeyError, ValueError):
        raise HTTPException(400, detail="Invalid export request") from None
    except OverflowError:
        raise HTTPException(429, detail="Export queue is full") from None


@router.get("/{ident}", response_model=ExportStatus)
def status(ident: str, request: Request, principal: Principal = session):
    try:
        return request.app.state.export_jobs.get(ident, principal.session_hash)
    except KeyError:
        raise HTTPException(404, detail="Export not found") from None


@router.get("/{ident}/file")
def file(ident: str, request: Request, principal: Principal = session):
    try:
        job = request.app.state.export_jobs.get(ident, principal.session_hash)
        if job["state"] != "complete" or not job["path"].is_file():
            raise KeyError(ident)
        chordpro = job["kind"] == "chordpro"
        return FileResponse(
            job["path"],
            media_type="text/plain" if chordpro else "application/zip",
            filename="song.chordpro" if chordpro else "songbook.zip",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
    except KeyError:
        raise HTTPException(404, detail="Export unavailable") from None
