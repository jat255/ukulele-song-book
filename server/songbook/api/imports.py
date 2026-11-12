"""Authenticated import and draft review endpoints."""

import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..imports.service import SUPPORTED, resolve_selection, scan_source_root
from ..storage.arrangements import ConflictError
from ..storage.db import connect
from .auth import Principal, require_csrf, require_session

router = APIRouter(prefix="/api/imports")
principal_dependency = Depends(require_session)


class ImportRequest(BaseModel):
    source_id: str
    selection: list[dict] = Field(min_length=1, max_length=20)
    method: Literal["direct", "local", "ai"]
    idempotency_key: str = Field(min_length=1, max_length=200)


class DraftEdit(BaseModel):
    source: str = Field(max_length=1_000_000)
    revision: str


class AcceptDraft(BaseModel):
    revision: str
    song_id: str | None = None
    acknowledge: bool = False


@router.post("/sources", status_code=201)
async def upload_source(
    request: Request, filename: str, principal: Principal = principal_dependency
):
    require_csrf(request, principal)
    name = Path(filename.replace("\\", "/")).name
    kind = Path(name).suffix.lower().lstrip(".")
    if kind not in {"pdf", "cho", "chordpro"}:
        raise HTTPException(400, detail="Unsupported source type")
    size = 0
    with tempfile.TemporaryFile() as stream:
        async for chunk in request.stream():
            size += len(chunk)
            if size > 100 * 1024 * 1024:
                raise HTTPException(413, detail="Source exceeds size limit")
            stream.write(chunk)
        stream.seek(0)
        source = request.app.state.store.register_source(stream, name, kind)
    return {"id": source.id, "kind": source.kind, "sha256": source.sha256}


@router.get("/sources")
def list_sources(request: Request, principal: Principal = principal_dependency):
    with connect(request.app.state.store.database) as db:
        rows = db.execute(
            "SELECT id,original_name,kind FROM sources ORDER BY original_name LIMIT 10000"
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("")
def list_jobs(request: Request, principal: Principal = principal_dependency):
    jobs = request.app.state.imports
    with connect(jobs.store.database) as db:
        ids = [
            row[0]
            for row in db.execute("SELECT id FROM import_jobs ORDER BY created_at DESC")
        ]
    return [jobs.get_job(ident) for ident in ids]


@router.post("", status_code=201)
def enqueue(
    body: ImportRequest, request: Request, principal: Principal = principal_dependency
):
    require_csrf(request, principal)
    try:
        return request.app.state.imports.enqueue_import(
            body.source_id, body.selection, body.method, body.idempotency_key
        )
    except ConflictError:
        raise HTTPException(
            409, detail="Request conflicts with an existing import"
        ) from None
    except (ValueError, KeyError):
        raise HTTPException(400, detail="Invalid import request") from None


class ScanSelection(BaseModel):
    path: str


@router.get("/roots")
def roots(request: Request, principal: Principal = principal_dependency):
    return {"roots": sorted(request.app.state.settings.source_roots)}


@router.get("/scan/{root_id}")
def scan(
    root_id: str,
    request: Request,
    path: str = ".",
    principal: Principal = principal_dependency,
):
    root = request.app.state.settings.source_roots.get(root_id)
    if root is None:
        raise HTTPException(404, detail="Input root not found")
    try:
        return {"files": scan_source_root(root, path)}
    except (ValueError, OSError):
        raise HTTPException(
            400, detail="Input root unavailable or selection invalid"
        ) from None


@router.post("/scan/{root_id}", status_code=201)
def register_scanned(
    root_id: str,
    body: ScanSelection,
    request: Request,
    principal: Principal = principal_dependency,
):
    require_csrf(request, principal)
    root = request.app.state.settings.source_roots.get(root_id)
    if root is None:
        raise HTTPException(404, detail="Input root not found")
    try:
        path = resolve_selection(root, body.path)
        if (
            not path.is_file()
            or path.name.startswith(".")
            or path.suffix.lower() not in SUPPORTED
        ):
            raise ValueError("Unsupported source")
        with path.open("rb") as stream:
            source = request.app.state.store.register_source(
                stream, path.name, path.suffix.lower()[1:]
            )
        return {"id": source.id, "kind": source.kind, "sha256": source.sha256}
    except (ValueError, OSError):
        raise HTTPException(400, detail="Input source unavailable or invalid") from None


@router.get("/{job_id}")
def get_job(job_id: str, request: Request, principal: Principal = principal_dependency):
    try:
        return request.app.state.imports.get_job(job_id)
    except KeyError:
        raise HTTPException(404, detail="Import not found") from None


class DiscardRequest(BaseModel):
    state: str = Field(max_length=30)
    drafts: dict[str, str] = Field(max_length=20)


@router.delete("/{job_id}", status_code=204)
def discard(
    job_id: str,
    body: DiscardRequest,
    request: Request,
    principal: Principal = principal_dependency,
):
    require_csrf(request, principal)
    try:
        request.app.state.imports.discard_job(job_id, body.state, body.drafts)
    except KeyError:
        raise HTTPException(404, detail="Import not found") from None
    except ConflictError:
        raise HTTPException(
            409, detail="Import changed or is processing; refresh and try again"
        ) from None


@router.put("/{job_id}/drafts/{draft_id}")
def edit(
    job_id: str,
    draft_id: str,
    body: DraftEdit,
    request: Request,
    principal: Principal = principal_dependency,
):
    require_csrf(request, principal)
    try:
        return request.app.state.imports.update_draft(
            job_id, draft_id, body.revision, body.source
        )
    except ConflictError:
        raise HTTPException(409, detail="Draft changed") from None


@router.post("/{job_id}/drafts/{draft_id}/accept")
def accept(
    job_id: str,
    draft_id: str,
    body: AcceptDraft,
    request: Request,
    principal: Principal = principal_dependency,
):
    require_csrf(request, principal)
    try:
        return asdict(
            request.app.state.imports.accept_draft(
                job_id,
                draft_id,
                body.revision,
                body.song_id,
                acknowledge=body.acknowledge,
            )
        )
    except ConflictError:
        raise HTTPException(409, detail="Draft changed") from None
    except KeyError:
        raise HTTPException(404, detail="Draft not found") from None
    except ValueError:
        raise HTTPException(400, detail="Draft cannot be accepted") from None


class RetryRequest(BaseModel):
    authorize_ai: bool = False


@router.post("/{job_id}/retry")
def retry(
    job_id: str,
    body: RetryRequest,
    request: Request,
    principal: Principal = principal_dependency,
):
    require_csrf(request, principal)
    try:
        return request.app.state.imports.retry_job(
            job_id, authorize_ai=body.authorize_ai
        )
    except KeyError:
        raise HTTPException(404, detail="Import not found") from None
    except ValueError:
        raise HTTPException(400, detail="Retry unavailable") from None


@router.get("/{job_id}/drafts/{draft_id}/suggestions")
def suggestions(
    job_id: str,
    draft_id: str,
    request: Request,
    principal: Principal = principal_dependency,
):
    try:
        return request.app.state.imports.suggest_duplicates(job_id, draft_id)
    except KeyError:
        raise HTTPException(404, detail="Draft not found") from None
