"""Local administration and server commands."""

import argparse
import getpass
import os
import sys
from pathlib import Path

from .config import Settings
from .main import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="songbook")
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth")
    auth.add_subparsers(dest="auth_command", required=True).add_parser("set-password")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    root = Path(os.environ.get("SONGBOOK_LIBRARY_ROOT", "./songbook-data"))
    if args.command == "auth":
        password = getpass.getpass("Password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation or len(password) < 12:
            print(
                "Passwords must match and contain at least 12 characters.",
                file=sys.stderr,
            )
            return 1
        create_app(Settings(library_root=root)).state.auth.set_password(password)
        return 0
    if args.host not in ("127.0.0.1", "::1", "localhost"):
        parser.error("Loopback HTTP mode requires a loopback host")
    import uvicorn

    origins = (
        f"http://127.0.0.1:{args.port}",
        f"http://localhost:{args.port}",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )
    uvicorn.run(
        create_app(Settings(library_root=root, allowed_origins=origins)),
        host=args.host,
        port=args.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
