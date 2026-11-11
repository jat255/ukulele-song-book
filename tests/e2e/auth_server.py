"""Synthetic, disposable API instance for the browser authentication test."""

import io
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from pypdf import PdfWriter

from server.songbook.config import Settings
from server.songbook.imports.worker import run_once
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
arrangement = app.state.store.create_arrangement(
    None,
    "{title: Browser Test}\n[C]Original\n{future: preserve}",
    [{"source_id": source.id, "pages": [1]}],
    None,
)
Path("/private/tmp/songbook-auth-e2e-arrangement-id").write_text(arrangement.id)
player_song = app.state.store.create_arrangement(
    None,
    "{title: Player Test}\n[C]Music\n{start_of_verse}\n"
    + "\n".join(f"[C]Line-{number:02}" for number in range(30))
    + "\n{end_of_verse}\n{start_of_tab}\n"
    + "\n".join(f"{string}|" + "-" * 100 + "|" for string in "AECG")
    + "\n{end_of_tab}",
    [],
    None,
)
Path("/private/tmp/songbook-auth-e2e-player-id").write_text(player_song.id)
writer = PdfWriter()
writer.add_blank_page(width=200, height=200)
writer.add_blank_page(width=200, height=200)
with Path("/private/tmp/songbook-auth-e2e-book.pdf").open("wb") as output:
    writer.write(output)


def work():
    while True:
        if not run_once(app.state.imports, "browser-test-worker"):
            time.sleep(0.2)


threading.Thread(target=work, daemon=True).start()
uvicorn.run(app, host="127.0.0.1", port=18765, log_level="warning")
