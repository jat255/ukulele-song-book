"""Authorize selected-page requests and retain submission identity."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

from ..music_bridge import parse_source
from .failures import ConversionFailure
from .models import ConversionDraft
from .providers.base import ProviderStatus, SelectedPage, VisionProvider, VisionRequest


@dataclass(frozen=True)
class PageSelection:
    source_id: str
    pages: list[SelectedPage]
    source_hash: str = ""


@dataclass(frozen=True)
class ConversionAuthorization:
    source_id: str
    page_hashes: tuple[str, ...]
    provider: str
    model: str
    explicit: bool
    nonce: str = ""
    page_numbers: tuple[int, ...] = ()
    source_hash: str = ""


class AIConversionService:
    def __init__(self, provider: VisionProvider | None, database: Path):
        self.provider = provider
        self.database = database
        with sqlite3.connect(database) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS vision_requests (identity TEXT PRIMARY KEY, state TEXT NOT NULL)"
            )

    def provider_status(self) -> ProviderStatus:
        return self.provider.status() if self.provider else ProviderStatus(False)

    def convert(self, selection: PageSelection, authorization: ConversionAuthorization):
        status = self.provider_status()
        hashes = tuple(hashlib.sha256(p.png).hexdigest() for p in selection.pages)
        if (
            not self.provider
            or not status.available
            or not authorization.explicit
            or not 1 <= len(selection.pages) <= status.page_limit
            or selection.source_id != authorization.source_id
            or not selection.source_hash
            or selection.source_hash != authorization.source_hash
            or hashes != authorization.page_hashes
            or tuple(p.page for p in selection.pages) != authorization.page_numbers
            or hashes != tuple(p.sha256 for p in selection.pages)
            or authorization.provider != status.provider
            or authorization.model != status.model
            or any(
                p.page < 1
                or len(p.png) > 12_000_000
                or not p.png.startswith(b"\x89PNG\r\n\x1a\n")
                for p in selection.pages
            )
        ):
            raise ValueError("Unauthorized or invalid page selection")
        try:
            for page in selection.pages:
                with Image.open(BytesIO(page.png)) as image:
                    if image.format != "PNG" or image.width * image.height > 12_000_000:
                        raise ValueError("Invalid page image")
                    image.verify()
        except (OSError, SyntaxError) as exc:
            raise ValueError("Invalid page image") from exc
        identity = hashlib.sha256(
            json.dumps(
                [
                    selection.source_id,
                    selection.source_hash,
                    [(p.page, p.sha256) for p in selection.pages],
                    status.provider,
                    status.model,
                    authorization.nonce,
                ]
            ).encode()
        ).hexdigest()
        try:
            with sqlite3.connect(self.database) as db:
                db.execute(
                    "INSERT INTO vision_requests VALUES (?, ?)", (identity, "submitted")
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Request already submitted; manual retry authorization required"
            ) from exc
        try:
            vision = self.provider.convert(VisionRequest(selection.pages))
            parse_source(vision.source)
            return ConversionDraft(
                song_id=selection.source_id,
                source=vision.source,
                pages=[p.page for p in selection.pages],
                source_refs=[
                    {
                        "source_id": selection.source_id,
                        "source_hash": selection.source_hash,
                        "page": p.page,
                        "page_hash": p.sha256,
                    }
                    for p in selection.pages
                ],
                uncertainty_spans=[
                    {
                        "start": 0,
                        "end": len(vision.source.encode("utf-16-le")) // 2,
                        "reason": "unverified provider draft",
                    }
                ],
                provider_metadata={
                    "request_id": vision.request_id,
                    "model": vision.model,
                    "usage": vision.usage,
                    "actual_cost": vision.actual_cost,
                    "quota_usage": vision.quota_usage,
                },
                needs_visual_review=True,
                diagnostics=[
                    "Provider output requires review",
                    *[str(x) for x in vision.uncertainties],
                ],
            )
        except ConversionFailure:
            raise
        except Exception:  # noqa: BLE001 - do not expose provider payloads
            raise ConversionFailure("draft_invalid") from None
