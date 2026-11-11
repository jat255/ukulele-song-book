"""Authenticated, separately revisioned grouped preferences."""

import hashlib
import json
from pathlib import Path
from typing import Generic, Literal, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..storage.db import connect
from .auth import Principal, require_csrf, require_session

router = APIRouter(prefix="/api/preferences")
session = Depends(require_session)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Play(StrictModel):
    fontPx: int = Field(default=20, ge=12, le=40)
    density: Literal["tight", "compact", "relaxed"] = "compact"
    columns: Literal["auto", 1, 2, 3] = "auto"
    scrollPxPerSecond: int = Field(default=15, ge=1, le=100)
    focus: bool = False


class Performance(StrictModel):
    semitones: int = Field(default=0, ge=-24, le=24)
    spelling: Literal["auto", "sharps", "flats"] = "auto"
    capo: int = Field(default=0, ge=0, le=12)
    tuning: Literal["high-g", "low-g"] = "high-g"


class Print(StrictModel):
    paper: Literal["Letter", "A4"] = "Letter"
    fontPt: int = Field(default=12, ge=8, le=24)
    density: Literal["tight", "compact", "relaxed"] = "compact"
    marginsMm: int = Field(default=8, ge=3, le=25)
    columns: Literal["auto", 1, 2] = "auto"
    diagrams: bool = False


T = TypeVar("T")


class Envelope(StrictModel, Generic[T]):  # noqa: UP046 - Pydantic generic model
    value: T
    updated_at: float = Field(default=0, ge=0, allow_inf_nan=False)
    device_id: str = Field(default="server", min_length=1, max_length=100)


class Groups(StrictModel):
    play: Envelope[Play] = Field(default_factory=lambda: Envelope(value=Play()))
    performance: Envelope[Performance] = Field(
        default_factory=lambda: Envelope(value=Performance())
    )
    print: Envelope[Print] = Field(default_factory=lambda: Envelope(value=Print()))


class Preferences(StrictModel):
    schema_version: Literal[1] = 1
    groups: Groups = Field(default_factory=Groups)


def initialize(database: Path) -> None:
    with connect(database) as db:
        db.executescript(
            (
                Path(__file__).parents[1] / "storage/migrations/005_preferences.sql"
            ).read_text()
        )


def encode(data: Preferences) -> tuple[str, str]:
    raw = json.dumps(data.model_dump(), sort_keys=True, separators=(",", ":"))
    return raw, hashlib.sha256(raw.encode()).hexdigest()


def read(db, ident: str) -> tuple[str, str]:
    if ident != "defaults":
        if not db.execute("SELECT 1 FROM arrangements WHERE id=?", (ident,)).fetchone():
            raise HTTPException(404, detail="Arrangement not found")
        row = db.execute(
            "SELECT document_json,etag FROM arrangement_preferences WHERE arrangement_id=?",
            (ident,),
        ).fetchone()
        if row:
            return row[0], row[1]
    row = db.execute(
        "SELECT document_json,etag FROM app_preferences WHERE id=1"
    ).fetchone()
    return (row[0], row[1]) if row else encode(Preferences())


@router.get("/{ident}", response_model=Preferences)
def get_preferences(
    ident: str, request: Request, response: Response, principal: Principal = session
):
    with connect(request.app.state.store.database) as db:
        raw, etag = read(db, ident)
    response.headers["ETag"] = etag
    return json.loads(raw)


@router.put("/{ident}", response_model=Preferences)
def put_preferences(
    ident: str,
    body: Preferences,
    request: Request,
    response: Response,
    if_match: str | None = Header(default=None),
    principal: Principal = session,
):
    require_csrf(request, principal)
    if not if_match:
        raise HTTPException(428, detail="Preference revision required")
    raw, etag = encode(body)
    with connect(request.app.state.store.database) as db:
        db.execute("BEGIN IMMEDIATE")
        _, current = read(db, ident)
        if current != if_match.strip('"'):
            raise HTTPException(409, detail="Preferences changed")
        if ident == "defaults":
            db.execute(
                "INSERT INTO app_preferences VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET document_json=excluded.document_json,etag=excluded.etag",
                (raw, etag),
            )
        else:
            db.execute(
                "INSERT INTO arrangement_preferences VALUES (?,?,?) ON CONFLICT(arrangement_id) DO UPDATE SET document_json=excluded.document_json,etag=excluded.etag",
                (ident, raw, etag),
            )
    response.headers["ETag"] = etag
    return body
