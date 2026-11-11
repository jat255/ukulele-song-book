"""Render a local source with the independently installed ChordPro tool."""

import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_suffix(".log").open("w") as log:
        subprocess.run(
            ["chordpro", "--output", str(args.output), str(args.source)],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=120,
        )


if __name__ == "__main__":
    main()
