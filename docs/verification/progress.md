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
