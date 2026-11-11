"""Bounded, read-only PDF extraction and page rasterization."""

from io import BytesIO
from pathlib import Path

import pdfplumber
import pypdfium2

from .models import PageExtraction

MAX_BYTES = 100 * 1024 * 1024
MAX_PAGES = 500
MAX_SELECTION = 20
MAX_PIXELS = 12_000_000


def extract_pages(path: Path, pages: list[int]) -> list[PageExtraction]:
    if (
        not pages
        or len(pages) > MAX_SELECTION
        or any(type(p) is not int or p < 1 for p in pages)
    ):
        raise ValueError("Invalid page selection")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("PDF exceeds size limit")
    try:
        with pdfplumber.open(path) as pdf:
            if len(pdf.pages) > MAX_PAGES or max(pages) > len(pdf.pages):
                raise ValueError("PDF or selection exceeds page limit")
            result = []
            for number in pages:
                page = pdf.pages[number - 1]
                keys = ("text", "x0", "x1", "top", "bottom", "upright")
                chars = [{key: char.get(key) for key in keys} for char in page.chars]
                words = page.extract_words()
                result.append(
                    PageExtraction(
                        number,
                        page.width,
                        page.height,
                        chars,
                        words,
                        True,
                        [
                            "Visual completeness requires review",
                            *(
                                ["Rotated text requires review"]
                                if any(c.get("upright") is False for c in chars)
                                else []
                            ),
                        ],
                    )
                )
            return result
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF could not be opened") from exc


def render_page(path: Path, page: int, dpi: int) -> bytes:
    if page < 1 or dpi < 1 or dpi > 600 or path.stat().st_size > MAX_BYTES:
        raise ValueError("Invalid rendering request")
    try:
        document = pypdfium2.PdfDocument(path)
        try:
            if len(document) > MAX_PAGES or page > len(document):
                raise ValueError("Invalid page")
            pdf_page = document[page - 1]
            width, height = pdf_page.get_size()
            scale = dpi / 72
            if width * scale * height * scale > MAX_PIXELS:
                raise ValueError("Page exceeds pixel limit")
            bitmap = pdf_page.render(scale=scale)
            try:
                output = BytesIO()
                bitmap.to_pil().save(output, format="PNG")
                return output.getvalue()
            finally:
                bitmap.close()
                pdf_page.close()
        finally:
            document.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF could not be rendered") from exc
