"""Frozen PDF inputs and actual artifact metadata."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ArrangementSnapshot:
    id: str
    song_id: str
    revision: str
    source: str
    source_refs: list[dict] = field(default_factory=list)
    document: dict | None = None


@dataclass(frozen=True)
class PerformanceSettings:
    semitones: int = 0
    spelling: str = "auto"
    capo: int = 0
    tuning: str = "high-g"


@dataclass(frozen=True)
class PrintSettings:
    paper: str = "Letter"
    font_pt: float = 12
    density: str = "compact"
    margins_mm: float = 8
    columns: int | str = "auto"
    diagrams: bool = False


@dataclass(frozen=True)
class PdfRenderRequest:
    source: str = ""
    output_dir: Path = Path(".")
    paper: str = "Letter"
    font_pt: float = 12
    columns: int | str = 1
    margins_mm: float = 8
    snapshots: list[ArrangementSnapshot] = field(default_factory=list)
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    settings: PrintSettings | None = None
    song_break: str = "page"


@dataclass(frozen=True)
class PdfArtifact:
    path: Path
    sha256: str
    page_count: int
    columns: int
    diagnostics: tuple[str, ...] = ()
