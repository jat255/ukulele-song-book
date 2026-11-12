"""Archive format and conservative resource limits."""

from dataclasses import dataclass

VERSION = 1
MAX_FILES = 100_000
MAX_TOTAL = 20 * 1024**3
MAX_FILE = 2 * 1024**3
MAX_MANIFEST = 32 * 1024**2


@dataclass(frozen=True)
class ExportManifest:
    version: int
    mode: str
    files: dict[str, dict]
    catalog: dict[str, list[dict]]


@dataclass(frozen=True)
class RestoreReport:
    mode: str
    files: int
