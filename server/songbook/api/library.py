"""Authenticated library metadata and arrangement operations."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from ..storage.arrangements import ConflictError
from .auth import Principal, require_csrf, require_session

router = APIRouter(prefix="/api")
session = Depends(require_session)


class MetadataEdit(BaseModel):
    revision: int
    favorite: bool
    tags: list[str] = Field(max_length=100)
    notes: str = Field(max_length=100_000)


class DeleteRequest(BaseModel):
    revision: int


class VariantRequest(BaseModel):
    source: str = Field(max_length=1_000_000)


@router.get("/library")
def search(
    request: Request,
    q: str = "",
    tag: Annotated[list[str] | None, Query()] = None,
    favorite: bool = False,
    recent: bool = False,
    principal: Principal = session,
):
    try:
        return request.app.state.library.search_library(
            q, tag or [], favorite, recent=recent
        )
    except ValueError:
        raise HTTPException(400, detail="Invalid search") from None


@router.get("/arrangements/{ident}/metadata")
def get_metadata(ident: str, request: Request, principal: Principal = session):
    try:
        return request.app.state.library.metadata(ident)
    except KeyError:
        raise HTTPException(404, detail="Arrangement not found") from None


@router.patch("/arrangements/{ident}/metadata")
def edit_metadata(
    ident: str, body: MetadataEdit, request: Request, principal: Principal = session
):
    require_csrf(request, principal)
    try:
        return request.app.state.library.update_metadata(
            ident,
            body.revision,
            favorite=body.favorite,
            tags=body.tags,
            notes=body.notes,
        )
    except KeyError:
        raise HTTPException(404, detail="Arrangement not found") from None
    except ConflictError:
        raise HTTPException(409, detail="Metadata changed") from None
    except ValueError:
        raise HTTPException(400, detail="Invalid metadata") from None


@router.post("/arrangements/{ident}/played", status_code=204)
def played(ident: str, request: Request, principal: Principal = session):
    require_csrf(request, principal)
    try:
        request.app.state.library.mark_played(ident)
    except KeyError:
        raise HTTPException(404, detail="Arrangement not found") from None
    return Response(status_code=204)


@router.post("/songs/{song_id}/arrangements", status_code=201)
def variant(
    song_id: str, body: VariantRequest, request: Request, principal: Principal = session
):
    require_csrf(request, principal)
    try:
        return asdict(
            request.app.state.store.create_arrangement(song_id, body.source, [], None)
        )
    except (KeyError, ValueError):
        raise HTTPException(404, detail="Song not found") from None


@router.delete("/arrangements/{ident}", status_code=204)
def delete(
    ident: str, body: DeleteRequest, request: Request, principal: Principal = session
):
    require_csrf(request, principal)
    try:
        request.app.state.library.delete(ident, body.revision)
    except KeyError:
        raise HTTPException(404, detail="Arrangement not found") from None
    except ConflictError:
        raise HTTPException(409, detail="Metadata changed") from None
    return Response(status_code=204)


@router.get("/arrangements/{ident}/download")
def download(ident: str, request: Request, principal: Principal = session):
    try:
        snapshot = request.app.state.store.get_arrangement(ident)
    except (KeyError, ValueError):
        raise HTTPException(404, detail="Arrangement not found") from None
    return Response(
        snapshot.source.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="arrangement.chordpro"',
            "X-Content-Type-Options": "nosniff",
        },
    )
