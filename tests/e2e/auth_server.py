"""Synthetic, disposable API instance for the browser authentication test."""

import io
import tempfile
from pathlib import Path

import uvicorn

from server.songbook.config import Settings
from server.songbook.main import create_app

root = Path(tempfile.mkdtemp(prefix="songbook-auth-e2e-"))
app = create_app(
    Settings(library_root=root, allowed_origins=("http://127.0.0.1:4173",))
)
app.state.auth.set_password("synthetic test password")
source = app.state.store.register_source(
    io.BytesIO(b"%PDF-1.4\n"), "synthetic.pdf", "pdf"
)
Path("/private/tmp/songbook-auth-e2e-source-id").write_text(source.id)
uvicorn.run(app, host="127.0.0.1", port=18765, log_level="warning")
