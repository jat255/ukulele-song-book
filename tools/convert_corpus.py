"""Produce private, explicitly unaccepted drafts for corpus review."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.songbook.imports.convert import convert_pages
from server.songbook.imports.models import SongRegion
from server.songbook.imports.pdf_extract import extract_pages
from tools.corpus import file_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    for sample in manifest["samples"]:
        originals = list(
            (args.manifest.parent / "originals").glob(sample["sha256"] + ".pdf")
        )
        if not originals:
            continue
        if file_hash(originals[0]) != sample["sha256"]:
            raise ValueError(f"Retained source hash mismatch: {sample['id']}")
        pages = extract_pages(originals[0], sample["pages"])
        draft = convert_pages(
            pages,
            [
                SongRegion(
                    sample["id"],
                    sample["id"],
                    sample["pages"],
                    source_hash=sample["sha256"],
                )
            ],
        )[0]
        (args.output / (sample["id"] + ".chordpro")).write_text(
            draft.source, encoding="utf-8"
        )
        (args.output / (sample["id"] + ".json")).write_text(
            json.dumps(asdict(draft), indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"{sample['id']}: {len(pages)} page(s), {len(draft.source)} draft characters; visual review required"
        )


if __name__ == "__main__":
    main()
