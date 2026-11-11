"""Render a frozen PDF request in a short-lived local process."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

from .models import PdfRenderRequest, PerformanceSettings, PrintSettings
from .render import render_pdf

request = json.load(sys.stdin)
performance = PerformanceSettings(**request["performance"])
settings = PrintSettings(**request["settings"])
try:
    artifact = render_pdf(
        PdfRenderRequest(
            source=request["source"],
            output_dir=Path(request["output_dir"]),
            performance=performance,
            settings=settings,
        )
    )
except ValueError as error:
    message = str(error)
    code = (
        "tab_too_tall"
        if "Tab exceeds available page height" in message
        else "tab_too_wide"
        if "Tab exceeds" in message
        else "content_too_wide"
        if "exceeds available column width" in message
        else "render_failed"
    )
    json.dump({"error_code": code}, sys.stdout)
else:
    result = asdict(artifact)
    result["path"] = str(artifact.path)
    json.dump(result, sys.stdout)
