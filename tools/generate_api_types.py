"""Generate or verify browser types against the local FastAPI schema."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.songbook.config import Settings
from server.songbook.main import create_app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = ROOT / "apps/web/src/api/generated.ts"
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        schema = create_app(Settings(library_root=tmp / "data")).openapi()
        (tmp / "openapi.json").write_text(json.dumps(schema, sort_keys=True))
        subprocess.run(
            [
                str(ROOT / "node_modules/.bin/openapi-typescript"),
                str(tmp / "openapi.json"),
                "-o",
                str(tmp / "generated.ts"),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        content = (tmp / "generated.ts").read_text()
    if args.check:
        if not output.exists() or output.read_text() != content:
            print(
                "API types are out of date; run npm run generate:api", file=sys.stderr
            )
            return 1
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
