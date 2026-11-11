"""Local storage configuration."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    library_root: Path
