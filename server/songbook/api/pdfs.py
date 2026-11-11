"""Authenticated creation and retrieval of frozen PDF artifacts."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..imports.pdf_extract import render_page
from ..pdf.jobs import QueueFull
from ..storage.arrangements import ConflictError
from .auth import Principal, require_csrf, require_session
from .preferences import Performance, Print

router = APIRouter(prefix="/api/pdfs")
session = Depends(require_session)


class PdfRequest(BaseModel):
    arrangement_id: str
    revision: str
    performance: Performance
    settings: Print


@router.post("", status_code=202)
def enqueue(body: PdfRequest, request: Request, principal: Principal = session):
    require_csrf(request, principal)
    performance = body.performance.model_dump()
    settings = body.settings.model_dump()
    settings = {
        "paper": settings["paper"],
        "font_pt": settings["fontPt"],
        "density": settings["density"],
        "margins_mm": settings["marginsMm"],
        "columns": settings["columns"],
        "diagrams": settings["diagrams"],
    }
    try:
        return request.app.state.pdf_jobs.enqueue(
            body.arrangement_id, body.revision, performance, settings
        )
    except QueueFull:
        raise HTTPException(429, detail="PDF queue is full; try again") from None
    except ConflictError:
        raise HTTPException(
            409, detail="Arrangement changed; refresh before printing"
        ) from None
    except (KeyError, ValueError):
        raise HTTPException(404, detail="Arrangement not found") from None


@router.get("/{job_id}")
def status(job_id: str, request: Request, principal: Principal = session):
    try:
        return request.app.state.pdf_jobs.get(job_id)
    except KeyError:
        raise HTTPException(404, detail="PDF job not found") from None


@router.get("/{job_id}/file")
def file(job_id: str, request: Request, principal: Principal = session):
    try:
        _, path = request.app.state.pdf_jobs.artifact(job_id)
        return Response(
            path.read_bytes(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="songbook.pdf"',
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )
    except (KeyError, ValueError, OSError):
        raise HTTPException(404, detail="PDF unavailable") from None


@router.get("/{job_id}/pages/{page}.png")
def page(job_id: str, page: int, request: Request, principal: Principal = session):
    try:
        job, path = request.app.state.pdf_jobs.artifact(job_id)
        if page < 1 or page > job["page_count"]:
            raise ValueError("Invalid page")
        with request.app.state.pdf_lock, request.app.state.store._lock():
            data = render_page(path, page, 100)
        return Response(
            data, media_type="image/png", headers={"Cache-Control": "no-store"}
        )
    except (KeyError, ValueError, OSError):
        raise HTTPException(404, detail="Page unavailable") from None
