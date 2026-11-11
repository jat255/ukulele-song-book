"""Local storage and authentication configuration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    library_root: Path
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    )
    loopback_http: bool = True
    session_seconds: int = 43200
    worker_required: bool = False
