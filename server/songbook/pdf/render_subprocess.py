"""Render a frozen PDF request in a short-lived local process."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

from .models import (
    ArrangementSnapshot,
    PdfRenderRequest,
    PerformanceSettings,
    PrintSettings,
)
from .render import render_pdf

request = json.load(sys.stdin)
performance = PerformanceSettings(**request.get("performance", {}))
snapshots = [
    ArrangementSnapshot(
        **{key: value for key, value in row.items() if key != "occurrence_id"}
    )
    for row in request.get("snapshots", [])
]
performances = [
    PerformanceSettings(**value) for value in request.get("performances", [])
]
settings = PrintSettings(**request["settings"])
try:
    artifact = render_pdf(
        PdfRenderRequest(
            source=request.get("source", ""),
            snapshots=snapshots,
            performances=performances,
            song_break=request.get("song_break", "new-page"),
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
