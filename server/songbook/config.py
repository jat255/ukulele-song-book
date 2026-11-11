"""Local storage and authentication configuration."""

from dataclasses import dataclass, field
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
    source_roots: dict[str, Path] = field(default_factory=dict)


def settings_from_environment() -> Settings:
    """Read local, operator-supplied paths; never trust paths from HTTP clients."""
    import json
    import os

    root = Path(os.environ.get("SONGBOOK_LIBRARY_ROOT", "./songbook-data"))
    raw = json.loads(os.environ.get("SONGBOOK_SOURCE_ROOTS", "{}"))
    if not isinstance(raw, dict) or any(
        not isinstance(key, str)
        or not key
        or not isinstance(value, str)
        or not Path(value).is_absolute()
        for key, value in raw.items()
    ):
        raise ValueError("Invalid source-root configuration")
    return Settings(
        library_root=root, source_roots={key: Path(value) for key, value in raw.items()}
    )
