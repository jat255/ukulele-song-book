"""Count managed PDF pages without rendering; isolated by the bounded caller."""

import hashlib
import json
import sys
from pathlib import Path

import pypdfium2

from .pdf_extract import MAX_BYTES, MAX_PAGES

request = json.load(sys.stdin)
path = Path(request["path"])
if path.stat().st_size > MAX_BYTES:
    raise ValueError("PDF exceeds size limit")
with path.open("rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != request["sha256"]:
        raise ValueError("Source changed")
document = pypdfium2.PdfDocument(path)
try:
    count = len(document)
    if not 1 <= count <= MAX_PAGES:
        raise ValueError("Unsupported page count")
    sys.stdout.write(str(count))
finally:
    document.close()
