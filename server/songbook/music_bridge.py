"""Controlled bridge to the shared source-preserving music parser."""

import json
import subprocess
import tempfile
import threading
from pathlib import Path


class MusicBridgeError(Exception):
    """The music parser was unavailable or returned an invalid response."""


def _run_bounded(
    command: list[str], request: str, *, limit: int, timeout: float
) -> str:
    with tempfile.TemporaryFile() as stdin:
        stdin.write(request.encode("utf-8"))
        stdin.seek(0)
        with subprocess.Popen(
            command, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        ) as process:
            chunks: list[bytes] = []
            overflow = threading.Event()

            def read_output() -> None:
                assert process.stdout is not None
                total = 0
                while chunk := process.stdout.read(65536):
                    total += len(chunk)
                    if total > limit:
                        overflow.set()
                        process.kill()
                        return
                    chunks.append(chunk)

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
            finally:
                reader.join(timeout=2)
            if overflow.is_set() or process.returncode != 0 or reader.is_alive():
                raise MusicBridgeError("Music parser failed or output exceeded limit")
            return b"".join(chunks).decode("utf-8")


def parse_source(source: str) -> dict:
    if len(source.encode("utf-8")) > 1_000_000:
        raise MusicBridgeError("Source exceeds parser limit")
    cli = Path(__file__).resolve().parents[2] / "packages/music/dist/cli.js"
    try:
        output = _run_bounded(
            ["node", str(cli)],
            json.dumps({"op": "parse", "source": source}),
            limit=8_000_000,
            timeout=10,
        )
        document = json.loads(output)["document"]
        if (
            not isinstance(document, dict)
            or document.get("schemaVersion") != 1
            or document.get("source") != source
            or not isinstance(document.get("blocks"), list)
        ):
            raise MusicBridgeError("Invalid parser document")
        return document
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        raise MusicBridgeError("Music parser failed") from exc
