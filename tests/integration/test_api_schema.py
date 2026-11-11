"""The checked-in browser contract must match the current API schema."""

import subprocess
import sys


def test_openapi_types_are_current():
    result = subprocess.run(
        [sys.executable, "tools/generate_api_types.py", "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
