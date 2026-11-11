# Implementation progress

Milestone 1 established private corpus selection, source-preserving parsing, review-only PDF extraction, a mocked optional vision boundary, and a shared browser/Chromium PDF feasibility renderer. See [the feasibility report](../feasibility/report.md) and [conversion results](../feasibility/conversion-results.md) for observed failures and remaining limits. No PDF conversion draft is accepted automatically. Per-sample correction times and complete manual error counts remain unmeasured; live vision fidelity remains unverified.

Run from the repository root after installing dependencies with `uv sync`, `npm ci`, and the matching Playwright Chromium browsers:

```sh
npm test --workspace @songbook/music
npm run build
npm exec playwright test tests/e2e/feasibility.spec.ts
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The next implementation task is M2.1, managed storage and recovery. No deployment or CI monitoring is authorized by these plans.
