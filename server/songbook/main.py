"""Authenticated local application API."""

import hashlib
import ipaddress
import os
import sqlite3
import tempfile
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path

import pypdfium2
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.auth import (
    COOKIE,
    AuthService,
    Principal,
    require_csrf,
    require_origin,
    require_session,
)
from .api.downloads import initialize as initialize_downloads
from .api.downloads import router as downloads_router
from .api.exports import ExportJobs
from .api.exports import router as exports_router
from .api.imports import router as imports_router
from .api.library import router as library_router
from .api.pdfs import router as pdf_router
from .api.preferences import initialize as initialize_preferences
from .api.preferences import router as preferences_router
from .api.schemas import (
    ArrangementResponse,
    EditRequest,
    LoginRequest,
    RestoreRequest,
    RevisionResponse,
    SessionResponse,
)
from .api.setlists import router as setlists_router
from .api.sync import router as sync_router
from .config import Settings
from .imports.jobs import ImportJobs
from .imports.pdf_extract import render_page
from .pdf.jobs import PdfJobs
from .storage.arrangements import ConflictError, LibraryStore, RecoveringError
from .storage.db import connect
from .storage.files import atomic_write
from .storage.library import LibraryIndex
from .storage.setlists import SetlistStore

_session_dependency = Depends(require_session)
_pdf_lock = threading.Lock()


def create_app(settings: Settings) -> FastAPI:
    store = LibraryStore(settings.library_root)
    store.recover_pending_writes()
    app = FastAPI()
    app.state.settings = settings
    app.state.store = store
    app.state.auth = AuthService(store.database, settings.session_seconds)
    app.state.imports = ImportJobs(store)
    app.state.library = LibraryIndex(store)
    app.state.setlists = SetlistStore(store)
    app.state.pdf_jobs = PdfJobs(store)
    app.state.export_jobs = ExportJobs(store)
    app.state.pdf_lock = _pdf_lock
    initialize_preferences(store.database)
    initialize_downloads(store)
    app.include_router(downloads_router)
    app.include_router(exports_router)
    app.include_router(imports_router)
    app.include_router(library_router)
    app.include_router(preferences_router)
    app.include_router(pdf_router)
    app.include_router(setlists_router)
    app.include_router(sync_router)

    @app.middleware("http")
    async def restrict_loopback(request: Request, call_next):
        if settings.loopback_http:
            try:
                local = bool(
                    request.client
                    and ipaddress.ip_address(request.client.host).is_loopback
                )
            except ValueError:
                local = False
            if not local:
                return JSONResponse(
                    status_code=403,
                    content={
                        "code": "forbidden",
                        "message": "Loopback access required",
                        "retryable": False,
                    },
                )
        elif request.url.scheme != "https":
            return JSONResponse(
                status_code=403,
                content={
                    "code": "forbidden",
                    "message": "HTTPS required",
                    "retryable": False,
                },
            )
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": {
                    401: "unauthorized",
                    403: "forbidden",
                    404: "not_found",
                    429: "rate_limited",
                }.get(exc.status_code, "request_error"),
                "message": str(exc.detail),
                "retryable": exc.status_code == 429,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_request",
                "message": "Invalid request",
                "retryable": False,
            },
        )

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        try:
            if not store.database.is_file():
                raise OSError("Database unavailable")
            with connect(store.database) as db:
                migrations = {
                    row[0]
                    for row in db.execute("SELECT version FROM schema_migrations")
                }
                if not {1, 2, 3, 4, 5, 6, 7, 8, 9}.issubset(migrations):
                    raise ValueError("Migrations incomplete")
                db.execute("BEGIN IMMEDIATE")
                db.rollback()
                if settings.worker_required:
                    row = db.execute(
                        "SELECT last_seen FROM worker_heartbeat WHERE id=1"
                    ).fetchone()
                    if not row or time.time() - row[0] > 360:
                        raise ValueError("Worker heartbeat unavailable")
            with tempfile.TemporaryFile(dir=store.root) as probe:
                probe.write(b"ok")
                probe.flush()
        except (OSError, sqlite3.Error, ValueError):
            raise HTTPException(503, detail="Service unavailable") from None
        return {"status": "ready"}

    @app.get("/api/provider")
    def provider_status(principal: Principal = _session_dependency):
        model = os.environ.get("SONGBOOK_ANTHROPIC_MODEL", "")
        configured = bool(model and os.environ.get("ANTHROPIC_API_KEY"))
        return {
            "provider": "anthropic",
            "model": model or None,
            "configured": configured,
            "available": configured
            and os.environ.get("SONGBOOK_ALLOW_EXTERNAL_AI") == "true",
            "cost_estimate": None,
        }

    @app.post("/api/session", response_model=SessionResponse)
    def login(body: LoginRequest, request: Request, response: Response):
        require_origin(request)
        token, csrf = app.state.auth.authenticate(
            body.password, request.client.host if request.client else "unknown"
        )
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            secure=not settings.loopback_http,
            samesite="strict",
            max_age=settings.session_seconds,
            path="/",
        )
        return {"csrf": csrf}

    @app.get("/api/session", response_model=SessionResponse)
    def session(principal: Principal = _session_dependency):
        return {"csrf": principal.csrf}

    @app.delete("/api/session", status_code=204)
    def logout(request: Request, principal: Principal = _session_dependency):
        require_csrf(request, principal)
        app.state.auth.revoke(principal)
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, path="/")
        return response

    def snapshot(ident: str):
        try:
            return store.get_arrangement(str(uuid.UUID(ident)))
        except (ValueError, KeyError):
            raise HTTPException(404, detail="Arrangement not found") from None
        except RecoveringError:
            raise HTTPException(503, detail="Arrangement recovering") from None

    @app.get("/api/arrangements/{ident}", response_model=ArrangementResponse)
    def arrangement(ident: str, principal: Principal = _session_dependency):
        return asdict(snapshot(ident))

    @app.put("/api/arrangements/{ident}", response_model=ArrangementResponse)
    def edit(
        ident: str,
        body: EditRequest,
        request: Request,
        if_match: str | None = Header(default=None),
        principal: Principal = _session_dependency,
    ):
        require_csrf(request, principal)
        current = snapshot(ident)
        if not if_match:
            raise HTTPException(428, detail="Revision required")
        try:
            return asdict(
                store.save_arrangement(current.id, if_match.strip('"'), body.source)
            )
        except ConflictError:
            latest = snapshot(ident)
            return JSONResponse(
                status_code=409,
                content={
                    "code": "revision_conflict",
                    "message": "Arrangement changed",
                    "retryable": False,
                    "details": {"current_revision": latest.revision},
                },
            )

    @app.get(
        "/api/arrangements/{ident}/revisions", response_model=list[RevisionResponse]
    )
    def revisions(ident: str, principal: Principal = _session_dependency):
        current = snapshot(ident)
        with connect(store.database) as db:
            rows = db.execute(
                "SELECT revision,created_at FROM revision_events WHERE arrangement_id=? ORDER BY id DESC",
                (current.id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @app.post("/api/arrangements/{ident}/restore", response_model=ArrangementResponse)
    def restore(
        ident: str,
        body: RestoreRequest,
        request: Request,
        if_match: str | None = Header(default=None),
        principal: Principal = _session_dependency,
    ):
        require_csrf(request, principal)
        current = snapshot(ident)
        if not if_match:
            raise HTTPException(428, detail="Revision required")
        try:
            return asdict(
                store.restore_revision(current.id, if_match.strip('"'), body.revision)
            )
        except KeyError:
            raise HTTPException(404, detail="Revision not found") from None
        except ConflictError:
            return JSONResponse(
                status_code=409,
                content={
                    "code": "revision_conflict",
                    "message": "Arrangement changed",
                    "retryable": False,
                    "details": {"current_revision": snapshot(ident).revision},
                },
            )

    def source_path(ident: str):
        try:
            ident = str(uuid.UUID(ident))
        except ValueError:
            raise HTTPException(404, detail="Source not found") from None
        with connect(store.database) as db:
            row = db.execute("SELECT * FROM sources WHERE id=?", (ident,)).fetchone()
        if not row:
            raise HTTPException(404, detail="Source not found")
        path = (store.root / row["path"]).resolve()
        if (
            not path.is_relative_to(store.root / "sources" / ident)
            or not path.is_file()
        ):
            raise HTTPException(404, detail="Source not found")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise HTTPException(503, detail="Source unavailable")
        return path, row["kind"], data

    @app.get("/api/sources/{ident}/original")
    def original(ident: str, principal: Principal = _session_dependency):
        path, kind, data = source_path(ident)
        valid_pdf = False
        if kind == "pdf":
            try:
                with _pdf_lock, store._lock():
                    document = pypdfium2.PdfDocument(path)
                    try:
                        valid_pdf = len(document) > 0
                    finally:
                        document.close()
            except (pypdfium2.PdfiumError, OSError, ValueError):
                valid_pdf = False
        media = "application/pdf" if valid_pdf else "application/octet-stream"
        headers = {
            "Content-Disposition": "inline" if valid_pdf else "attachment",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        }
        if kind == "pdf" and not valid_pdf:
            headers["X-Songbook-Source-Error"] = "invalid_pdf"
        return Response(
            data,
            media_type=media,
            headers=headers,
        )

    @app.get("/api/sources/{ident}/pages/{page}.png")
    def source_page(ident: str, page: int, principal: Principal = _session_dependency):
        path, kind, _ = source_path(ident)
        if kind != "pdf":
            raise HTTPException(400, detail="Source is not a PDF")
        try:
            if page < 1 or page > 500:
                raise ValueError("Invalid page")
            derivative = (
                store.root / "derivatives" / str(uuid.UUID(ident)) / f"{page}-100.png"
            )
            with _pdf_lock, store._lock():
                if derivative.is_file():
                    image = derivative.read_bytes()
                else:
                    image = render_page(path, page, 100)
                    atomic_write(derivative, image)
            return Response(image, media_type="image/png")
        except ValueError:
            raise HTTPException(400, detail="Page unavailable") from None

    web_dist = Path(__file__).resolve().parents[2] / "apps/web/dist"
    if web_dist.is_dir():

        @app.get("/imports", include_in_schema=False)
        @app.get("/player", include_in_schema=False)
        @app.get("/edit", include_in_schema=False)
        @app.get("/print", include_in_schema=False)
        @app.get("/login", include_in_schema=False)
        @app.get("/settings", include_in_schema=False)
        @app.get("/setlists", include_in_schema=False)
        @app.get("/set-player", include_in_schema=False)
        @app.get("/set-print", include_in_schema=False)
        def web_shell():
            return FileResponse(web_dist / "index.html")

        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app
