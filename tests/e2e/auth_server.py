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
print_song = app.state.store.create_arrangement(None, arrangement.source, [], None)
Path("/private/tmp/songbook-auth-e2e-print-id").write_text(print_song.id)
player_song = app.state.store.create_arrangement(
    None,
    "{title: Player Test}\n[C]Music\n[C][D][Em][G]\n{start_of_verse}\n"
    + "\n".join(f"[C]Line-{number:02}" for number in range(30))
    + "\n{end_of_verse}\n{start_of_tab}\n"
    + "\n".join(f"{string}|" + "-" * 100 + "|" for string in "AECG")
    + "\n{end_of_tab}",
    [],
    None,
)
Path("/private/tmp/songbook-auth-e2e-player-id").write_text(player_song.id)
for index in range(5):
    layout_song = app.state.store.create_arrangement(
        None,
        player_song.source.replace(
            "{title: Player Test}", f"{{title: Player Test Layout {index}}}"
        ),
        [],
        None,
    )
    Path(f"/private/tmp/songbook-auth-e2e-layout-{index}-id").write_text(layout_song.id)
app.state.store.create_arrangement(
    None,
    player_song.source.replace("{title: Player Test}", "{title: Setlist Player Test}"),
    [],
    None,
)
performance_song = app.state.store.create_arrangement(
    None,
    player_song.source.replace("{title: Player Test}", "{title: Performance Test}"),
    [],
    None,
)
Path("/private/tmp/songbook-auth-e2e-performance-id").write_text(performance_song.id)
writer = PdfWriter()
writer.add_blank_page(width=200, height=200)
writer.add_blank_page(width=200, height=200)
with Path("/private/tmp/songbook-auth-e2e-book.pdf").open("wb") as output:
    writer.write(output)


# A portable synthetic batch for browser review tests.
import hashlib
import zipfile
from uuid import uuid4

from server.songbook.bulk.manifest import BatchEntry, BatchManifest

pdf_data = Path("/private/tmp/songbook-auth-e2e-book.pdf").read_bytes()
draft_data = b"{title: Batch Test}\n[C]Hello"
entry = BatchEntry(
    entry_id=uuid4(),
    source_name="batch.pdf",
    source_sha256=hashlib.sha256(pdf_data).hexdigest(),
    original_path="originals/test.pdf",
    page_count=2,
    decision="include",
    state="completed",
    draft_path="drafts/test.cho",
    draft_sha256=hashlib.sha256(draft_data).hexdigest(),
)
manifest = BatchManifest(batch_id=uuid4(), entries=[entry])
with zipfile.ZipFile("/private/tmp/songbook-e2e-batch.zip", "w") as archive:
    archive.writestr("manifest.json", manifest.model_dump_json())
    archive.writestr(entry.original_path, pdf_data)
    archive.writestr(entry.draft_path, draft_data)


def work():
    while True:
        if not run_once(
            app.state.imports, "browser-test-worker", pdf_jobs=app.state.pdf_jobs
        ):
            time.sleep(0.2)


threading.Thread(target=work, daemon=True).start()
uvicorn.run(app, host="127.0.0.1", port=18765, log_level="warning")
