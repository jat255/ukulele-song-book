import json
import subprocess
from unittest.mock import patch

import pytest

from server.songbook.music_bridge import MusicBridgeError, parse_source


def test_parse_bridge():
    assert parse_source("[C]Hello")["source"] == "[C]Hello"


@pytest.mark.parametrize(
    "output", ["not json", "{}", json.dumps({"document": {"source": "different"}})]
)
def test_invalid_output_is_rejected(output):
    with (
        patch(
            "server.songbook.music_bridge._run_bounded",
            return_value=output,
        ),
        pytest.raises(MusicBridgeError),
    ):
        parse_source("hello")


def test_timeout_is_controlled():
    with (
        patch(
            "server.songbook.music_bridge._run_bounded",
            side_effect=subprocess.TimeoutExpired("node", 1),
        ),
        pytest.raises(MusicBridgeError),
    ):
        parse_source("hello")


def test_oversized_output_is_rejected():
    with (
        patch(
            "server.songbook.music_bridge._run_bounded",
            return_value=subprocess.CompletedProcess(
                [], 0, stdout="x" * 8_000_001, stderr=""
            ),
        ),
        pytest.raises(MusicBridgeError),
    ):
        parse_source("hello")


def test_cli_output_limit_is_enforced_during_execution(tmp_path):
    from server.songbook.music_bridge import _run_bounded

    script = tmp_path / "flood.py"
    script.write_text(
        'import sys\nwhile True: sys.stdout.write("x" * 65536); sys.stdout.flush()\n'
    )
    import sys

    with pytest.raises(MusicBridgeError):
        _run_bounded([sys.executable, str(script)], "{}", limit=100000, timeout=3)
