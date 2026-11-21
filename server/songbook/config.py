"""Local storage and authentication configuration."""

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ALLOWED_ORIGINS = ("http://127.0.0.1:8000", "http://localhost:8000")


@dataclass(frozen=True)
class Settings:
    library_root: Path
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS
    loopback_http: bool = True
    session_seconds: int = 43200
    worker_required: bool = False
    source_roots: dict[str, Path] = field(default_factory=dict)


def settings_from_environment() -> Settings:
    """Read local, operator-supplied paths; never trust paths from HTTP clients."""
    import json
    import os
    from urllib.parse import urlsplit

    root = Path(os.environ.get("SONGBOOK_LIBRARY_ROOT", "./songbook-data"))
    origin = os.environ.get("SONGBOOK_PUBLIC_ORIGIN")
    if origin:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("SONGBOOK_PUBLIC_ORIGIN must be an HTTPS origin")
        try:
            _port = parsed.port
        except ValueError as error:
            raise ValueError("Invalid public origin port") from error
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
        library_root=root,
        allowed_origins=(origin,) if origin else DEFAULT_ALLOWED_ORIGINS,
        loopback_http=not bool(origin),
        source_roots={key: Path(value) for key, value in raw.items()},
        worker_required=os.environ.get("SONGBOOK_WORKER_REQUIRED") == "true",
    )
