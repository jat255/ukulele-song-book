"""Render one PDF page in an isolated, bounded subprocess."""

import base64
import json
import sys
from pathlib import Path

from .pdf_extract import render_page

request = json.load(sys.stdin)
sys.stdout.write(
    base64.b64encode(render_page(Path(request["path"]), request["page"], 100)).decode(
        "ascii"
    )
)
