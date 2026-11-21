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
    bulk = commands.add_parser("bulk")
    bulk_commands = bulk.add_subparsers(dest="bulk_command", required=True)
    scan = bulk_commands.add_parser("inventory")
    scan.add_argument("--source", type=Path, required=True)
    scan.add_argument("--output", type=Path, required=True)
    selection = bulk_commands.add_parser("select")
    selection.add_argument("--output", type=Path, required=True)
    selection.add_argument("--include", action="append", default=[])
    selection.add_argument("--exclude", action="append", default=[])
    selection.add_argument(
        "--include-remaining",
        action="store_true",
        help="Include all still-pending PDFs after reviewing and excluding songbooks",
    )
    selection.add_argument("--reason")
    convert = bulk_commands.add_parser("convert")
    convert.add_argument("--source", type=Path, required=True)
    convert.add_argument("--output", type=Path, required=True)
    preview = bulk_commands.add_parser(
        "preview", help="Render PDFs for completed drafts without using Codex"
    )
    preview.add_argument("--output", type=Path, required=True)
    batch_export = bulk_commands.add_parser("export")
    batch_export.add_argument("--output", type=Path, required=True)
    batch_export.add_argument("--archive", type=Path, required=True)
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
    if args.command == "bulk":
        from .bulk.inventory import inventory, select

        if args.bulk_command == "inventory":
            manifest = inventory(args.source, args.output)
            print(f"Inventoried {len(manifest.entries)} PDFs; all require a decision.")
        elif args.bulk_command == "select":
            if not args.include and not args.exclude and not args.include_remaining:
                parser.error("select requires --include or --exclude")
            for name in args.include:
                select(args.output, name, "include")
            for name in args.exclude:
                select(args.output, name, "exclude", args.reason)
            if args.include_remaining:
                from .bulk.manifest import load_manifest

                manifest = load_manifest(args.output / "manifest.json")
                for entry in manifest.entries:
                    if entry.decision == "pending":
                        select(args.output, entry.source_name, "include")
        elif args.bulk_command == "convert":
            from .bulk.convert import convert_batch, render_preview

            preview_errors = []

            def preview_draft(root, entry):
                try:
                    print(f"PDF preview: {render_preview(root, entry)}", flush=True)
                except Exception as error:  # noqa: BLE001 - preview failures must not discard completed drafts
                    preview_errors.append(entry.source_name)
                    print(
                        f"Preview failed for {entry.source_name}: {error}",
                        file=sys.stderr,
                        flush=True,
                    )

            print("Codex sends document content online and uses your subscription.")
            result = convert_batch(args.source, args.output, on_completed=preview_draft)
            for entry in result.entries:
                detail = f": {entry.error['message']}" if entry.error else ""
                print(f"{entry.source_name}: {entry.state}{detail}")
            if preview_errors or any(
                entry.decision == "include" and entry.state != "completed"
                for entry in result.entries
            ):
                return 1
        elif args.bulk_command == "preview":
            from .bulk.convert import render_previews

            paths = render_previews(args.output)
            for path in paths:
                print(f"PDF preview: {path}")
            if not paths:
                print("No completed drafts to preview.")
        else:
            from .bulk.convert import export_batch

            export_batch(args.output, args.archive)
        return 0
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
        create_app(
            replace(settings, allowed_origins=origins)
            if settings.loopback_http
            else settings
        ),
        host=args.host,
        port=args.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
