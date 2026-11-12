"""Create an operational snapshot containing private authentication state."""

from pathlib import Path

from ..storage.arrangements import LibraryStore
from .export import _archive
from .manifest import ExportManifest


def backup_library(store: LibraryStore, destination: Path) -> ExportManifest:
    return _archive(store, destination, "backup")
