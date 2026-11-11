"""Private subprocess boundary for bounded local PDF extraction."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

from .convert import convert_pages
from .models import SongRegion
from .pdf_extract import extract_pages


def main() -> None:
    request = json.load(sys.stdin)
    regions = []
    for index, part in enumerate(request["selection"]):
        rects = {
            int(page): tuple(coords)
            for page, coords in part.get("rectangles", {}).items()
        }
        regions.append(
            SongRegion(
                str(index),
                part.get("label", ""),
                part["pages"],
                rects,
                request["sha256"],
            )
        )
    pages = sorted({page for region in regions for page in region.pages})
    drafts = convert_pages(extract_pages(Path(request["path"]), pages), regions)
    json.dump([asdict(draft) for draft in drafts], sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
