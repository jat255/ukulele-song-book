"""Generate review-only drafts from explicit page regions."""

import re

from .models import ConversionDraft, PageExtraction, SongRegion
from .reading_order import order_columns


def attach_chords(chars: list[dict], chords: list[dict]) -> str:
    chars = sorted(chars, key=lambda char: char["x0"])
    anchors: dict[int, list[str]] = {}
    for chord in chords:
        index = (
            min(range(len(chars)), key=lambda i: abs(chars[i]["x0"] - chord["x0"]))
            if chars
            else 0
        )
        anchors.setdefault(index, []).append(chord["text"])
    return "".join(
        "".join(f"[{chord}]" for chord in anchors.get(i, [])) + char["text"]
        for i, char in enumerate(chars)
    ) + "".join(f"[{chord}]" for chord in anchors.get(len(chars), []))


def convert_pages(
    pages: list[PageExtraction], regions: list[SongRegion]
) -> list[ConversionDraft]:
    by_page = {page.page: page for page in pages}
    drafts = []
    for region in regions:
        if not region.pages or any(number not in by_page for number in region.pages):
            raise ValueError("Region references unavailable pages")
        result = []
        for number in region.pages:
            page = by_page[number]
            rect = region.rectangles.get(number, (0, 0, 1, 1))
            x0, y0, x1, y1 = rect
            if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                raise ValueError("Invalid region rectangle")
            words = [
                w
                for w in page.words
                if w["x0"] >= x0 * page.width
                and w["x1"] <= x1 * page.width
                and w["top"] >= y0 * page.height
                and w["bottom"] <= y1 * page.height
            ]
            ordered = order_columns(words, page.width)
            lines: list[list[dict]] = []
            for word in ordered:
                if (
                    lines
                    and abs(lines[-1][0]["top"] - word["top"]) <= 3
                    and word["x0"] >= lines[-1][-1]["x1"]
                ):
                    lines[-1].append(word)
                else:
                    lines.append([word])
            index = 0
            while index < len(lines):
                line = lines[index]
                if re.match(r"^[A-Ga-g](?:#|b)?\s*\|", line[0]["text"]):
                    tab_lines = []
                    while index < len(lines) and re.match(
                        r"^[A-Ga-g](?:#|b)?\s*\|", lines[index][0]["text"]
                    ):
                        tab_line = lines[index]
                        tab_chars = [
                            c
                            for c in page.chars
                            if c.get("top") is not None
                            and abs(c["top"] - tab_line[0]["top"]) <= 3
                            and c["x0"] >= x0 * page.width
                            and c["x1"] <= x1 * page.width
                        ]
                        tab_lines.append(
                            "".join(
                                c["text"]
                                for c in sorted(tab_chars, key=lambda c: c["x0"])
                            )
                            if tab_chars
                            else " ".join(w["text"] for w in tab_line)
                        )
                        index += 1
                    result.extend(["{start_of_tab}", *tab_lines, "{end_of_tab}"])
                    continue
                chord_line = all(
                    re.fullmatch(
                        r"[A-G](?:#|b)?(?:m|maj|min|dim|aug|sus|add|[0-9+#()/b-])*",
                        word["text"],
                    )
                    for word in line
                )
                if chord_line and index + 1 < len(lines):
                    next_line = lines[index + 1]
                    delta = next_line[0]["top"] - line[0]["bottom"]
                    lyric_chars = [
                        c
                        for c in page.chars
                        if c.get("top") is not None
                        and abs(c["top"] - next_line[0]["top"]) <= 3
                        and c["x0"] >= x0 * page.width
                        and c["x1"] <= x1 * page.width
                    ]
                    if 0 <= delta <= 12 and lyric_chars:
                        result.append(attach_chords(lyric_chars, line))
                        index += 2
                        continue
                result.append(" ".join(word["text"] for word in line))
                index += 1
        drafts.append(
            ConversionDraft(
                region.song_id,
                "\n".join(result),
                region.pages,
                [
                    {
                        "source_hash": region.source_hash,
                        "page": n,
                        "rectangle": region.rectangles.get(n, (0, 0, 1, 1)),
                    }
                    for n in region.pages
                ],
                [
                    {
                        "start": 0,
                        "end": len("\n".join(result).encode("utf-16-le")) // 2,
                        "reason": "unverified extraction",
                    }
                ]
                if result
                else [],
                True,
                [
                    "Draft requires manual visual review; inferred chord alignment may be inaccurate",
                    *(
                        message
                        for n in region.pages
                        for message in by_page[n].diagnostics
                    ),
                    *(
                        ["No text could be extracted; consult the original page"]
                        if not result
                        else []
                    ),
                ],
            )
        )
    return drafts


def preferred_source(chordpro: str, draft: str, verified: bool) -> str:
    """Prefer a separately verified transcription to an extraction draft."""
    return chordpro if verified else draft
