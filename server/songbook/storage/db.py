"""SQLite connection and schema initialization."""

import sqlite3
from pathlib import Path


class ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, traceback):
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path, timeout=10, factory=ManagedConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    db.execute("PRAGMA journal_mode=WAL")
    return db


def initialize(path: Path) -> None:
    sql = (Path(__file__).parent / "migrations/001_library.sql").read_text()
    with connect(path) as db:
        db.executescript(sql)
