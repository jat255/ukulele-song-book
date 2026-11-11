"""Public API input contracts."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str = Field(max_length=1024)


class EditRequest(BaseModel):
    source: str = Field(max_length=1_000_000)


class RestoreRequest(BaseModel):
    revision: str = Field(min_length=64, max_length=64)


class SessionResponse(BaseModel):
    csrf: str


class SourceReference(BaseModel):
    source_id: str
    pages: list[int]
    crop_asset_id: str | None = None


class ArrangementResponse(BaseModel):
    id: str
    song_id: str
    revision: str
    source: str
    document: dict
    source_refs: list[SourceReference]


class RevisionResponse(BaseModel):
    revision: str
    created_at: str
