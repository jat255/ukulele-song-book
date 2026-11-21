"""Single-user sessions with Argon2, bounded failures and CSRF checks."""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request

from ..storage.db import connect

COOKIE = "songbook_session"


@dataclass(frozen=True)
class Principal:
    session_hash: str
    csrf: str


class AuthService:
    def __init__(self, database: Path, session_seconds: int):
        self.database = database
        self.session_seconds = session_seconds
        self.hasher = PasswordHasher()
        with connect(database) as db:
            db.executescript(
                (
                    Path(__file__).parents[1] / "storage/migrations/002_auth.sql"
                ).read_text()
            )

    def set_password(self, password: str) -> None:
        if len(password) < 12:
            raise ValueError("Password must contain at least 12 characters")
        password_hash = self.hasher.hash(password)
        with connect(self.database) as db:
            db.execute(
                "INSERT INTO auth_config VALUES (1,?) ON CONFLICT(id) DO UPDATE SET password_hash=excluded.password_hash",
                (password_hash,),
            )
            db.execute("DELETE FROM sessions")

    def authenticate(self, password: str, client: str) -> tuple[str, str]:
        now = time.time()
        with connect(self.database) as db:
            db.execute("DELETE FROM login_failures WHERE occurred_at < ?", (now - 60,))
            if db.execute("SELECT count(*) FROM login_failures").fetchone()[0] >= 2000:
                raise HTTPException(429, detail="Too many attempts")
            if (
                db.execute(
                    "SELECT count(*) FROM login_failures WHERE client=?", (client,)
                ).fetchone()[0]
                >= 5
            ):
                raise HTTPException(429, detail="Too many attempts")
            row = db.execute(
                "SELECT password_hash FROM auth_config WHERE id=1"
            ).fetchone()
            try:
                valid = bool(row and self.hasher.verify(row["password_hash"], password))
            except VerificationError:
                valid = False
            if not valid:
                db.execute("INSERT INTO login_failures VALUES (?,?)", (client, now))
            else:
                db.execute("DELETE FROM login_failures WHERE client=?", (client,))
                token = secrets.token_urlsafe(32)
                csrf = secrets.token_urlsafe(32)
                db.execute(
                    "INSERT INTO sessions VALUES (?,?,?)",
                    (
                        hashlib.sha256(token.encode()).hexdigest(),
                        csrf,
                        now + self.session_seconds,
                    ),
                )
        if not valid:
            raise HTTPException(401, detail="Invalid credentials")
        return token, csrf

    def principal(self, token: str | None) -> Principal:
        if not token:
            raise HTTPException(401, detail="Authentication required")
        digest = hashlib.sha256(token.encode()).hexdigest()
        with connect(self.database) as db:
            row = db.execute(
                "SELECT csrf,expires_at FROM sessions WHERE id_hash=?", (digest,)
            ).fetchone()
        if not row or row["expires_at"] <= time.time():
            raise HTTPException(401, detail="Authentication required")
        return Principal(digest, row["csrf"])

    def local_session(self) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        with connect(self.database) as db:
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?)",
                (
                    hashlib.sha256(token.encode()).hexdigest(),
                    csrf,
                    time.time() + self.session_seconds,
                ),
            )
        return token, csrf

    def revoke(self, principal: Principal) -> None:
        with connect(self.database) as db:
            db.execute(
                "DELETE FROM sessions WHERE id_hash=?", (principal.session_hash,)
            )

    def clear_failures(self):
        with connect(self.database) as db:
            db.execute("DELETE FROM login_failures")

    def expire_all(self):
        with connect(self.database) as db:
            db.execute("UPDATE sessions SET expires_at=0")


def require_session(request: Request) -> Principal:
    return request.app.state.auth.principal(request.cookies.get(COOKIE))


def require_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origins:
        raise HTTPException(403, detail="Origin rejected")


def require_csrf(request: Request, principal: Principal) -> None:
    require_origin(request)
    token = request.headers.get("x-csrf-token", "")
    if not hmac.compare_digest(token, principal.csrf):
        raise HTTPException(403, detail="CSRF token rejected")
