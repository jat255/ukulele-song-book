"""Portable batch manifest and atomic persistence."""

from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from ..storage.files import atomic_write


class BatchEntry(BaseModel):
    entry_id: UUID
    source_name: str
    source_sha256: str
    original_path: str
    page_count: int = 0
    decision: Literal["pending", "include", "exclude"] = "pending"
    exclusion_reason: str | None = None
    state: Literal["pending", "running", "completed", "failed", "interrupted"] = (
        "pending"
    )
    draft_path: str | None = None
    draft_sha256: str | None = None
    diagnostics: list[str] = Field(default_factory=list)
    uncertainties: list[dict] = Field(default_factory=list)
    error: dict | None = None

    @field_validator("original_path", "draft_path", "source_name")
    @classmethod
    def relative_path(cls, value: str | None) -> str | None:
        if value is not None:
            path = PurePosixPath(value)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in value
                or not path.parts
            ):
                raise ValueError("Expected a safe relative path")
        return value


class BatchManifest(BaseModel):
    schema_version: Literal[1] = 1
    batch_id: UUID
    entries: list[BatchEntry]


def load_manifest(path: Path) -> BatchManifest:
    return BatchManifest.model_validate_json(path.read_bytes())


def save_manifest(path: Path, manifest: BatchManifest) -> None:
    atomic_write(path, (manifest.model_dump_json(indent=2) + "\n").encode())
