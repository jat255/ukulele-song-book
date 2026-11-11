# Private ukulele songbook

The songbook is under development. The current milestone provides managed storage,
a private API, and the beginning of the authenticated shell; import, library,
player, printing, and offline workflows are not yet complete.

For local development, install Python 3.12+, Node 22.12+, uv, and dependencies:

```sh
uv sync
npm ci
npm run build
export SONGBOOK_LIBRARY_ROOT="$PWD/songbook-data"
uv run songbook auth set-password
uv run songbook serve --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The password is prompted without echo and only its
Argon2 hash is stored. Replacing it revokes existing sessions. Keep the managed
library directory private and outside version control; it contains originals,
arrangements, and authentication data. For frontend development start `npm run
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
