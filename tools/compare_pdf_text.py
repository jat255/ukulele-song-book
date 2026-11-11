"""Report aggregate lyric-fragment extraction counts without logging content."""

import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.songbook.music_bridge import parse_source


def tokens(value: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFKD", value).lower())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    doc = parse_source(args.source.read_bytes().decode("utf-8"))
    expected = collections.Counter(
        word
        for block in doc["blocks"]
        if block["kind"] == "lyric"
        for segment in block["segments"]
        for word in tokens(segment["lyric"])
    )
    actual = collections.Counter(
        tokens("\n".join(page.extract_text() for page in PdfReader(args.pdf).pages))
    )
    print(
        json.dumps(
            {
                "lyric_fragment_tokens": sum(expected.values()),
                "unmatched_tokens": sum((expected - actual).values()),
            }
        )
    )


if __name__ == "__main__":
    main()
