"""Read-only input-root scanning, confined to configured directories."""

from pathlib import Path

SUPPORTED = {".pdf", ".cho", ".chordpro"}


def resolve_selection(root: Path, relative: str) -> Path:
    root = root.resolve(strict=True)
    supplied = Path(relative)
    if supplied.is_absolute() or ".." in supplied.parts:
        raise ValueError("Invalid selection")
    path = (root / supplied).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError("Selection outside input root")
    return path


def scan_source_root(root: Path, relative: str) -> list[str]:
    base = resolve_selection(root, relative)
    root = root.resolve(strict=True)
    if not base.is_dir():
        raise ValueError("Selection is not a directory")
    found = []
    for path in base.rglob("*"):
        if path.name.startswith(".") or path.suffix.lower() not in SUPPORTED:
            continue
        if (
            path.is_symlink()
            or not path.is_file()
            or not path.resolve().is_relative_to(root)
        ):
            continue
        found.append(path.relative_to(root).as_posix())
        if len(found) > 10000:
            raise ValueError("Selection exceeds scan limit")
    return sorted(found)
