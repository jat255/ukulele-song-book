# Implementation progress

Milestone 1 established source-preserving parsing, review-only PDF extraction,
a mocked optional vision boundary, and the initial browser/Chromium renderer.
See [the feasibility report](../feasibility/report.md) and
[conversion results](../feasibility/conversion-results.md). No PDF conversion
draft is accepted automatically. Detailed per-page error counts and correction
times are unmeasured; live vision fidelity is unverified.

Milestone 2 implements managed storage and recovery, private sessions, reviewed
imports, the searchable library and editor, the responsive player, performance
controls, saved preferences, and individual PDF preview/export. Local evidence
and limits are in [online songbook verification](online-songbook.md). The
rasterized real-song PDF pages have not been visually inspected, so absence of
visual clipping is not verified. Phone viewport checks use emulation; a physical
phone has not been tested.

Run from the repository root after installing dependencies with `uv sync`,
`npm ci`, and the matching Playwright Chromium browser:

```sh
npm test --workspace @songbook/music
npm test --workspace @songbook/web
npm run typecheck
npm run build
npm exec playwright test
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python tools/generate_api_types.py --check
```

See the README for local password provisioning, server and worker commands.
The next milestone adds setlists, offline use and portability. No deployment,
publication, push, external collection submission or CI monitoring is authorized
by these plans.

Milestone 3 has local setlist, offline download and reconnection work in
progress. See [offline verification](offline.md) for browser versions,
reconciliation behavior and the physical-device limitations. These results do
not establish portability, backup/restore, local container operation, or
milestone completion; those require their own gates.

M3 portability work includes a synthetic backup restored to a separate local
library. Authentication, retained original bytes, metadata, search, and two
ordered occurrences were checked; the restored song produced a one-page PDF.
A standalone synthetic ChordPro export was also opened by the independent
ChordPro command-line renderer. These are synthetic checks, not evidence of
visual inspection of real-song raster pages or physical-phone behavior.
Portable extraction drafts remain review-only; live vision fidelity and
per-page correction times remain unmeasured.

M3 consolidated local checks: `uv run --offline pytest -q` passed 205 tests;
`npm test --workspaces --if-present` passed 5 web and 24 music tests;
`npm run typecheck`, `npm run build`, `npm run check:api`, `ruff check .`, and
`ruff format --check .` passed. The full Chromium Playwright run passed 84
tests with `--workers=1`. An earlier full run had four failures caused by
saved synthetic player preferences leaking between tests; isolated test
arrangements were added and the affected eight tests and full suite passed.
Prior M3 synchronization checks passed 19 tests in persistent WebKit profiles;
private/transient WebKit storage remains unverified.

Docker Desktop built and started the Linux ARM image and worker locally.
A synthetic song was imported, reviewed, edited, played, previewed as a
one-page PDF, downloaded and opened offline with transposition; restart
preserved it. A backup restored into a separate volume passed authentication
and search. No private corpus or provider request was used. Compose defaults to
host loopback; it is not a remote deployment configuration.

Resume local operation and restoration with `docker compose up -d` and the
commands in [local-running.md](../local-running.md) and
[backup-restore.md](../backup-restore.md). The complete ruling ledger and
stated costs are in [rulings.md](rulings.md). Real-song raster-page visual
inspection, physical-phone and live vision checks remain unverified; PDF
drafts remain review-only and detailed correction times/error counts remain
unmeasured.

The container acceptance used `docker compose -p songbook-m3-verification
up -d --no-build`, then `docker compose -p songbook-m3-verification restart`.
It created a synthetic backup with `docker compose -p
songbook-m3-verification exec -T api songbook backup --output
/tmp/synthetic-backup.zip`; a network-disabled one-off container restored that
archive with `songbook restore --archive /input/backup.zip --destination
/restore/library --mode backup` into a separate named volume. The local test
credentials and generated artifacts are synthetic and are not included here.

The final whole-branch review is in [branch-review.md](branch-review.md). Its
export-catalog memory-bound fix passed a targeted regression and 41 focused
portability, restore, and recovery tests after the consolidated run above.

## Review follow-up — 2026-11-12

Addressed review feedback inline from clean base 119535e. See
[comment outcomes](review-comments.md) for every comment, evidence, decisions,
and remaining limits. This follow-up changes local UI, diagram lookup, preview
resolution and automatic song caching; M4 remains unauthorized. Prior M1–M3
completion evidence is retained rather than overwritten.

Second review follow-up: replaced expanding library disclosures with floating
popovers, moved chord overview above music with a hide toggle, rebuilt settings
spacing and the grouped session panel, and added distinct play/print choosers.
Final Chromium suite: 87 passed; unit suite: 5 web +25 music passed;
production build, typecheck and diff whitespace checks passed. Inline review
caught and fixed setlist-ID leakage into arrangement navigation (RED→GREEN).
See review-comments.md for details and preserved validation limits.

Capo/tuning/hint follow-up: full-row capo and spinner removal, removed high/low-G
UI, portal chord hints and correct non-triad slash-bass voicings. Final Chromium
89 passed, focused WebKit 4 passed, web/music unit 5+26 passed; typecheck/build
and diff check passed. Screenshot and inline final review completed. Prior
corpus/provider/physical-device limits unchanged.

Library table follow-up: storage estimates and visible offline status removed;
compact semantic table with Favorite/Song/Artist/Tags/Actions and optional More
popover. Full Chromium91, focused WebKit7, units5+26, typecheck/build/diff passed.
Desktop/phone-emulation screenshots and inline final review completed. Existing
corpus/provider/physical-device limitations retained.
