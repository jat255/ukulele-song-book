"""Authenticated setlist resources."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..storage.arrangements import ConflictError
from .auth import Principal, require_csrf, require_session

router = APIRouter(prefix="/api/setlists")
session = Depends(require_session)


class CreateSet(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SetItem(BaseModel):
    id: str
    arrangementId: str


class SaveSet(CreateSet):
    revision: str
    items: list[SetItem] = Field(max_length=500)


class DeleteSet(BaseModel):
    revision: str


@router.get("")
def list_sets(request: Request, principal: Principal = session):
    return request.app.state.setlists.list()


@router.post("", status_code=201)
def create(body: CreateSet, request: Request, principal: Principal = session):
    require_csrf(request, principal)
    try:
        return request.app.state.setlists.create(body.title)
    except ValueError:
        raise HTTPException(400, detail="Invalid setlist") from None


@router.get("/{ident}")
def get(ident: str, request: Request, principal: Principal = session):
    try:
        return request.app.state.setlists.get(ident)
    except KeyError:
        raise HTTPException(404, detail="Setlist not found") from None


@router.put("/{ident}")
def save(ident: str, body: SaveSet, request: Request, principal: Principal = session):
    require_csrf(request, principal)
    try:
        return request.app.state.setlists.save_setlist(
            ident, body.revision, body.title, [item.model_dump() for item in body.items]
        )
    except KeyError:
        raise HTTPException(404, detail="Setlist not found") from None
    except ConflictError:
        raise HTTPException(409, detail="Setlist changed") from None
    except (ValueError, TypeError):
        raise HTTPException(400, detail="Invalid setlist") from None


@router.delete("/{ident}", status_code=204)
def delete(
    ident: str, body: DeleteSet, request: Request, principal: Principal = session
):
    require_csrf(request, principal)
    try:
        request.app.state.setlists.delete(ident, body.revision)
    except KeyError:
        raise HTTPException(404, detail="Setlist not found") from None
    except ConflictError:
        raise HTTPException(409, detail="Setlist changed") from None
    return Response(status_code=204)
