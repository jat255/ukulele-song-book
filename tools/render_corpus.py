"""Render selected original ChordPro sources locally for review."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.songbook.pdf.models import PdfRenderRequest
from server.songbook.pdf.render import render_pdf
from tools.corpus import file_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    for sample in manifest["samples"]:
        files = [
            path
            for path in (args.manifest.parent / "originals").glob(
                sample["sha256"] + ".*"
            )
            if path.suffix in {".cho", ".chordpro"}
        ]
        if not files:
            continue
        if file_hash(files[0]) != sample["sha256"]:
            raise ValueError("Source hash mismatch")
        artifact = render_pdf(
            PdfRenderRequest(
                files[0].read_bytes().decode("utf-8"), args.output, columns="auto"
            )
        )
        print(
            f"{sample['id']}: {artifact.page_count} pages, {artifact.columns} columns, hash {artifact.sha256}"
        )


if __name__ == "__main__":
    main()
