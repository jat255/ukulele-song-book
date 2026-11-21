"""Provider-neutral selected-page vision contracts."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SelectedPage:
    page: int
    png: bytes
    sha256: str


@dataclass(frozen=True)
class VisionRequest:
    pages: list[SelectedPage]


@dataclass(frozen=True)
class VisionDraft:
    source: str
    uncertainties: list
    model: str
    usage: dict
    request_id: str
    actual_cost: float | None = None
    quota_usage: dict | None = None


@dataclass(frozen=True)
class ProviderStatus:
    available: bool
    provider: str = ""
    model: str = ""
    page_limit: int = 5
    estimated_cost: float | None = None
    rate_basis: dict | None = None


class VisionProvider(Protocol):
    def convert(self, request: VisionRequest) -> VisionDraft: ...
    def status(self) -> ProviderStatus: ...
