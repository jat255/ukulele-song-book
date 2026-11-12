"""Local administration and server commands."""

import argparse
import getpass
import sys
from dataclasses import replace
from pathlib import Path

from .config import settings_from_environment
from .main import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="songbook")
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth")
    auth.add_subparsers(dest="auth_command", required=True).add_parser("set-password")
    commands.add_parser("worker")
    for command in ("export", "backup"):
        archive = commands.add_parser(command)
        archive.add_argument("--output", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    restore.add_argument("--mode", choices=("portable", "backup"), required=True)
    commands.add_parser("reindex")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    settings = settings_from_environment()
    root = settings.library_root
    if args.command == "restore":
        from .portability.restore import restore_archive

        restore_archive(args.archive, args.destination, args.mode)
        return 0
    if args.command in ("export", "backup", "reindex"):
        from .storage.arrangements import LibraryStore

        store = LibraryStore(root)
        if args.command == "export":
            from .portability.export import export_library

            export_library(store, args.output)
        elif args.command == "backup":
            from .portability.backup import backup_library

            backup_library(store, args.output)
        else:
            store.recover_pending_writes()
        return 0
    if args.command == "auth":
        password = getpass.getpass("Password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation or len(password) < 12:
            print(
                "Passwords must match and contain at least 12 characters.",
                file=sys.stderr,
            )
            return 1
        create_app(settings).state.auth.set_password(password)
        return 0
    if args.command == "worker":
        from .imports.jobs import ImportJobs
        from .imports.worker import run_worker
        from .storage.arrangements import LibraryStore

        run_worker(ImportJobs(LibraryStore(root)))
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
        create_app(replace(settings, allowed_origins=origins)),
        host=args.host,
        port=args.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
