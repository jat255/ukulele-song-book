"""Data structures for explicitly reviewable PDF extraction."""

from dataclasses import dataclass, field


@dataclass
class PageExtraction:
    page: int
    width: float
    height: float
    chars: list[dict]
    words: list[dict]
    needs_visual_review: bool = True
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class SongRegion:
    song_id: str
    label: str
    pages: list[int]
    rectangles: dict[int, tuple[float, float, float, float]] = field(
        default_factory=dict
    )
    source_hash: str = ""


@dataclass
class ConversionDraft:
    song_id: str
    source: str
    pages: list[int]
    source_refs: list[dict] = field(default_factory=list)
    uncertainty_spans: list[dict] = field(default_factory=list)
    needs_visual_review: bool = True
    diagnostics: list[str] = field(default_factory=list)
    provider_metadata: dict = field(default_factory=dict)
