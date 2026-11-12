"""Bounded revision checks that never mutate local or canonical copies."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..storage.arrangements import RecoveringError
from ..storage.db import connect
from .auth import Principal, require_csrf, require_session

router = APIRouter(prefix="/api/sync")
session = Depends(require_session)


class KnownRevision(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    revision: str = Field(max_length=128)


class SyncCheck(BaseModel):
    arrangements: list[KnownRevision] = Field(default_factory=list, max_length=500)
    setlists: list[KnownRevision] = Field(default_factory=list, max_length=100)


@router.post("/check")
def check(body: SyncCheck, request: Request, principal: Principal = session):
    require_csrf(request, principal)
    store = request.app.state.store
    arrangements = []
    setlists = []
    with store._lock(), connect(store.database) as db:
        db.execute("BEGIN")
        for known in body.arrangements:
            row = db.execute(
                "SELECT a.revision,COALESCE(m.deleted,0) AS deleted FROM arrangements a LEFT JOIN library_metadata m ON m.arrangement_id=a.id WHERE a.id=?",
                (known.id,),
            ).fetchone()
            revision = None
            if not row:
                state = "unavailable"
            elif row["deleted"]:
                state = "deleted"
            else:
                try:
                    snapshot = store._read_locked(db, known.id)
                    revision = snapshot.revision
                    state = "current" if revision == known.revision else "outdated"
                except (KeyError, RecoveringError, ValueError):
                    state = "unavailable"
            arrangements.append({"id": known.id, "revision": revision, "state": state})
        for known in body.setlists:
            row = db.execute(
                "SELECT revision FROM setlists WHERE id=?", (known.id,)
            ).fetchone()
            revision = row["revision"] if row else None
            state = (
                ("current" if revision == known.revision else "outdated")
                if row
                else (
                    "deleted"
                    if db.execute(
                        "SELECT 1 FROM setlist_tombstones WHERE id=?", (known.id,)
                    ).fetchone()
                    else "unavailable"
                )
            )
            setlists.append({"id": known.id, "revision": revision, "state": state})
    return {"arrangements": arrangements, "setlists": setlists}
