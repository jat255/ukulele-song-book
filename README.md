# Private ukulele songbook

The songbook provides a private managed library, reviewed imports, playing,
setlists, printing, offline downloads, and local export and backup. See
[local running](docs/local-running.md) for the container setup and
[deployment readiness](docs/deployment-readiness.md) for remaining limits.

For local development, install Python 3.12+, Node 22.12+, uv, and dependencies:

```sh
uv sync
npm ci
npm run build
export SONGBOOK_LIBRARY_ROOT="$PWD/songbook-data"
uv run songbook serve --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The local app opens without a password. Keep it bound to loopback and keep the managed
library directory private and outside version control; it contains originals and arrangements. For frontend development start `npm run
dev` separately and open the displayed loopback URL; Vite proxies the API to
port 8000. The development server is intended for the local machine only.

Check the generated API contract with `npm run check:api`, or regenerate it
with `npm run generate:api`. Run `uv run pytest`, `npm run typecheck`,
`npm run build`, and `npm exec playwright test` for local checks after installing
Playwright's Chromium. Browser tests start disposable synthetic services locally.

PDF extraction is experimental and creates review-only drafts. The original
source must be retained and conversion results require human review. Live vision
conversion fidelity has not been verified. No external provider is contacted
by these local commands.

Run the durable import worker in a second terminal with the same
`SONGBOOK_LIBRARY_ROOT`:

```sh
uv run songbook worker
```

The Imports page accepts local PDF and ChordPro files. For PDFs, enter one-based
page numbers separated by commas, and separate songs with semicolons. Optional
normalized crop coordinates apply to the chosen pages. Every PDF extraction
requires review against the retained original. Empty extraction cannot be
accepted as music; add and review the missing notation first.

To browse optional read-only input directories, set `SONGBOOK_SOURCE_ROOTS` to a
JSON object mapping names to absolute local directories before starting the
server. The application copies selected sources into managed storage and does
not modify the input folders. Keep machine-specific paths out of version control.

The optional vision adapter is disabled unless the operator sets
`SONGBOOK_ALLOW_EXTERNAL_AI=true`, `ANTHROPIC_API_KEY`, and
`SONGBOOK_ANTHROPIC_MODEL` in the server and worker environments. In that mode,
the review screen requires an explicit action naming the provider and selected
full pages; costs may be unknown. Provider responses and fidelity have not been
verified live. Do not enable it unless external submission and possible charges
are authorized.
