# Personal Ukulele Songbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task, inline. Steps use checkbox (`- [ ]`) syntax for tracking. Do not delegate unless separately authorized by the active session.

**Goal:** Deliver a portable private ukulele library with reviewed imports, dense playing and printing, and downloaded songs and setlists for offline use.

**Architecture:** Keep canonical ChordPro and originals in a managed directory; SQLite owns app metadata, jobs, and rebuildable search indexes. A shared TypeScript music package feeds the React client and a controlled Chromium PDF renderer; a Python API and one durable background worker own storage and expensive work. Prove conversion and rendering before choosing the production parser and extraction implementation.

**Tech Stack:** React/TypeScript with Vite; Python 3.12+ with FastAPI, Uvicorn, sqlite3, pytest and Ruff; npm workspaces, Vitest and Playwright; SQLite FTS5; locally bundled fonts; Docker Compose packaging. ChordSheetJS, pdfplumber and pypdfium2 are initial feasibility candidates, not measured successes or final parser/conversion commitments.

**Spec:** `docs/superpowers/specs/2026-11-10-ukulele-songbook-design.md` (approved 2026-11-11).

## Global Constraints

The three milestone plans inherit this section; quoted requirements are from the approved design.

- “Information density is the primary layout requirement.”
- “ChordPro is the authoritative editable song format. The original PDFs remain preserved attachments.”
- “Preserve unsupported directives and original source text on round trips.”
- “Supported import formats are PDF and ChordPro (`.chordpro` and `.cho`); folder scans ignore other file types.”
- “Tablature transposition is deferred.”
- “Standard GCEA is the initial tuning; support low-G as an explicit distinction where pitch-dependent behavior requires it.”
- “Text size, density, and columns are separately adjustable.”
- “Honor the chosen text size; provide density, margins, and columns before considering smaller text.”
- “Support Letter and A4 initially.”
- “Editing requires a connection initially.”
- “Reject concurrent source edits using revision checks rather than silently overwriting another browser's edit.”
- “Provider credentials remain on the server.”
- “Use authenticated access over HTTPS; do not expose an unauthenticated PDF library on the internet.”
- Source folders are read-only inputs. Never commit the collection, private conversion outputs, credentials, or machine-specific source paths.
- No deployment, publishing, pushes, remote repositories, infrastructure changes, or GitHub CI monitoring in this work. Milestone 4 needs a separate deployment instruction.
- This planning session stops after writing and checking these plans. No dependency installation, corpus creation, product code, service startup, or implementation commits now.

## Review Focus

1. Crash between canonical-file replacement and index update: recovery must expose a consistent accepted revision (M2 task 1).
2. Vector-only lyrics and ambiguous columns: report incompleteness and retain originals instead of accepting empty or reordered music (M1 task 3).
3. Wider adjacent transposed chords and oversized tab: preserve anchors, complete string groups and readable text size (M2 tasks 5 and 7).
4. Retried imports and conflicting browser edits: no duplicate accepted arrangements or lost revisions (M2 tasks 1–3).
5. Partial browser-cache eviction or deleted server songs: offline status must reflect actual availability (M3 task 2).

## Workspace evidence and scope

Inspected on 2026-11-11: HEAD `74ceb1e`; tracked files are the approved design and `.gitignore`. `IMPLEMENTATION_PROMPT.md` is untracked user material; leave it untouched and out of implementation commits. The reviewed mockup is present and was read. The NAS directory is readable, and `uv`, `node`, and the independent `chordpro` command exist; their versions and actual runtime behavior have not been validated here. No app checks have run because there is no app yet.

Read the design in full at execution time. The handoff's earlier instruction to execute is superseded for this session by Josh's explicit request to stop at the plan.

## Execution sequence

| Order | Plan | Independently reviewable result | Gate |
| --- | --- | --- | --- |
| 1 | [Conversion and portability](2026-11-11-songbook-m1-feasibility.md) | Reproducible private corpus, draft conversion, lossless-source parser boundary, independent exports and a measured report | Resolve or explicitly limit unsupported cases before M2 |
| 2 | [Useful online songbook](2026-11-11-songbook-m2-online.md) | Durable managed library, import review, editing, dense player, transpose/diagrams and real individual PDF preview/export | Browser and PDF evidence on real imports |
| 3 | [Setlists, offline and portability](2026-11-11-songbook-m3-offline-portability.md) | Ordered sets, authenticated downloads, truthful offline state, setlist PDFs, portable export/restore and local container packaging | Offline target-browser checks and clean restore |
| 4 | Separate future deployment plan | Chosen host, identity integration, HTTPS and remote access | Separate instruction; no deployment commands in these plans |

Proceed in order inline when implementation is authorized. Each task follows a failing regression test, observed failure, minimal implementation, passing local verification, and focused commit. Do not add tests for trivial scaffolding. Tests below cover music fidelity, durability or user behavior. A task's file list includes its tests; root manifests/lockfiles change only when that task first needs a dependency. Commit exact task-owned paths, preserving unrelated files.

## Builder decisions and dependency selection

- Use one repository with `apps/web`, `packages/music`, `server`, `tests/e2e`, and `tools`. Python commands run from the root with `uv run`; JS commands run from the root npm workspace. Use Node 22.12+ (or a currently supported later LTS) and Python 3.12+; verify compatibility before resolving and commit `package-lock.json` and `uv.lock` during M1 task 1.
- Use `sqlite3` with migrations, WAL on local persistent disk, foreign keys, busy timeouts and bounded transactions. Avoid Redis/Celery for a personal library: one worker leases persisted jobs from SQLite.
- Keep parser semantics in `packages/music`; Python invokes its built JSON CLI for indexing/conversion validation. The browser imports the same functions for online/offline playing. Do not implement a second ChordPro grammar in Python.
- Keep raw source alongside a derived rendering model. ChordSheetJS is a candidate behind an adapter, never the sole container for unknown directives. M1 decides whether to retain its semantic parser or use a narrow source-preserving parser behind the same interface.
- Start extraction evaluation with pdfplumber character/word coordinates and pypdfium2 page rasterization. Compare PyMuPDF only if the initial pair fails measurable needs; record capabilities and licensing before adoption. Do not classify vector-heavy documents using image counts.
- Use Python Playwright's pinned Chromium and the web music components for production PDFs; inspect resulting PDF bytes with pypdf and render pages for visual checks. PDF preview displays the resulting artifact, never an estimated HTML page count.
- Ship one optional Anthropic Messages vision adapter as a builder choice, behind a provider-neutral interface. Model name and credentials are server configuration with no paid model default. Use selected page images, explicit action and bounded output. If access or spending authorization is absent, run contract tests only and state live fidelity is unverified.
- Bundle licensed text and monospace fonts locally, including license files; do not depend on third-party font requests. Start with Noto Serif and Noto Sans Mono, verify glyph coverage during M1, and pin assets by checksum.
- Use a single-user local password/session implementation for a safe runnable application; deployment may replace it with a trusted identity integration. No public signup or multi-library schema. Packaging binds to loopback by default.

## File ownership and shared interfaces

| Location | Responsibility |
| --- | --- |
| `packages/music/src/model.ts` | Serializable derivative music model and diagnostics |
| `packages/music/src/{source,parser,transpose,diagrams}.ts` | Lossless source edits, parsing adapter, performance transforms and validated uke shapes |
| `packages/music/src/cli.ts` | stdin/stdout JSON bridge for the Python worker |
| `apps/web/src/music/` | Shared screen/print React music blocks and fonts |
| `server/songbook/storage/` | Managed files, revisions, recovery and SQL migrations |
| `server/songbook/imports/` | Source registration, extraction, selected-page conversion and durable jobs |
| `server/songbook/api/` | Authenticated HTTP routes and schemas |
| `server/songbook/pdf/` | Browser PDF generation, artifact metadata and bounded jobs |
| `apps/web/src/features/` | Library, imports, player, print, sets, offline and settings workspaces |
| `tests/fixtures/synthetic/` | Authored/public-domain test content only |
| `.local/corpus/`, `.local/evidence/` | Ignored private fixtures and screenshots/PDFs |
| `docs/feasibility/`, `docs/verification/` | Reproducible methodology, redacted measurements and limitations |

Use these names throughout all three plans (types may be extended without changing their meaning):

```ts
type RevisionId = string; // SHA-256 of exact canonical UTF-8 bytes
type Diagnostic = { code: string; severity: 'info'|'warning'|'error';
  message: string; line?: number; page?: number };
type SourceSpan = { start: number; end: number }; // UTF-16 source offsets
type MusicDocument = { schemaVersion: 1; source: string;
  metadata: Record<string, string[]>; blocks: MusicBlock[];
  definitions: ChordDefinition[]; diagnostics: Diagnostic[] };
type MusicBlock = LyricLine | TabBlock | SectionBoundary | CommentBlock | DirectiveBlock | UnsupportedBlock;
// LyricLine: ordered segments {chord?: string, lyric: string, span: SourceSpan}[];
// TabBlock: exact text, optional label, complete string-group boundaries;
// DirectiveBlock: ordered metadata/key/capo/transpose directives with name/value/span;
// remaining blocks carry source span and literal text/label as applicable.
type PerformanceSettings = { semitones: number; spelling: 'auto'|'sharps'|'flats';
  capo: number; tuning: 'high-g'|'low-g' };
type PlaySettings = { fontPx: number; density: 'tight'|'compact'|'relaxed';
  columns: 'auto'|1|2|3; scrollPxPerSecond: number; focus: boolean };
type PrintSettings = { paper: 'Letter'|'A4'; fontPt: number;
  density: 'tight'|'compact'|'relaxed'; marginsMm: number;
  columns: 'auto'|1|2; diagrams: boolean };
type ArrangementSnapshot = { id: string; songId: string; revision: RevisionId;
  source: string; document: MusicDocument; sourceRefs: SourceReference[] };
type SourceReference = { sourceId: string; pages: number[]; cropAssetId?: string };
```

IDs are UUIDs except revision/content hashes. Page numbers in app contracts are **one-based**; convert at PDF-library boundaries. Sources and revisions are immutable; metadata updates use resource revision checks. Define concrete discriminated block types in M1 task 2. Python Pydantic API models produce OpenAPI; generate TS API types in M2 task 2. Store canonical source UTF-8 bytes separately from TS offsets; non-UTF-8 uploads require explicit encoding review, never silent replacement characters.

## Verification and evidence rules

- Author synthetic fixtures with unique section/line IDs and assertions on chord offsets. Keep private lyric text and rendered collection pages out of Git, reports, normal logs and provider payload snapshots.
- Every milestone report lists commands, dependency/browser/font versions, sample IDs, pass/fail/unsupported results and remaining limits. A skipped live provider or real phone check is visibly unverified, never a pass.
- M1 records per sample: source hash/pages, text/column detection, missing/extra lines, wrong chord anchors, tab fidelity, review minutes, provenance and independent-renderer result. Do not advertise collection-wide accuracy from a small corpus.
- M2 verifies 1440×900 laptop and 390×844 phone layouts, narrow 320px stress, larger text and a long section/tab fixture. M3 additionally requires real laptop/phone browser offline checks; automation in Chromium/WebKit is supplemental.
- For PDFs check actual media size, page count, text completeness with repeats, no clipped/out-of-bounds music, tab alignment and embedded fonts. Inspect rasterized pages; do not infer visual correctness solely from extracted text.
- After each milestone update `docs/verification/progress.md` with completed tasks, exact local run/resume commands and limitations. No GitHub CI checks.

## Documentation references consulted 2026-11-11

These establish API capabilities, not tested fitness. Recheck release docs at dependency resolution and record selected versions in `docs/feasibility/dependencies.md`.

- [ChordPro tab sections](https://www.chordpro.org/chordpro/directives-env_tab/): tab text remains literal except the terminating directive.
- [ChordPro key/capo semantics](https://www.chordpro.org/chordpro/directives-key/) and [scoped transpose](https://www.chordpro.org/chordpro/directives-transpose/): scope changes and capo must survive rendering/export.
- [ChordPro CLI](https://www.chordpro.org/chordpro/using-chordpro/): independent rendering and version capture.
- [ChordSheetJS upstream documentation](https://github.com/martijnversluis/ChordSheetJS): ChordPro parsing/formatting and chord transformations; corpus verification still required.
- [pdfplumber upstream documentation](https://github.com/jsvine/pdfplumber): coordinate-bearing word and character extraction; layout text is not a guarantee of reading order.
- [pypdfium2 API](https://pypdfium2.readthedocs.io/en/stable/python_api.html): candidate page rendering; confirm during M1 selection.
- [Playwright PDF API](https://playwright.dev/python/docs/api/class-page#page-pdf): use print media, `scale=1` and CSS page sizing with `prefer_css_page_size=True` to avoid implicit scaling.
- [Vite setup](https://vite.dev/guide/), [FastAPI workers](https://fastapi.tiangolo.com/deployment/server-workers/), [Python sqlite3](https://docs.python.org/3/library/sqlite3.html): baseline tooling and process/storage boundaries.
- [Anthropic vision](https://platform.claude.com/docs/en/build-with-claude/vision): selected images in Messages requests; provider access/fidelity untested.
- [Browser persistent storage](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/persist): persistence is a request, not a guarantee; verify cached assets directly.

## Coverage and handoff

| Design area | Owning tasks |
| --- | --- |
| Conversion corpus, PDF reading order, tab fallback, portability proof | M1.1–M1.5 |
| Original retention, managed canonical storage, recovery, revisions | M2.1 |
| Private access, source fallback, validated routes | M2.2 |
| Durable import/review, multi-song pages, optional AI configuration | M1.3–4, M2.3 |
| Search/favorites/tags/recent/variants and editing | M2.4 |
| Dense columns, phone controls, focus and tab handling | M2.5 |
| Transpose/capo/diagrams, scroll/awake, practice notes/preferences | M2.6 |
| Actual PDF preview, page optimization and browser printing | M1.5, M2.7 |
| Ordered setlists, offline downloads, stale states/preferences | M3.1–3 |
| Full portable export, backup and tested restore | M3.4 |
| Health/resource limits and reproducible local containers | M2.2–3, M2.7, M3.5 |
| Host/hostname/identity/remote HTTPS deployment | Future separately authorized M4 |

Planning self-review: all design sections mapped above; shared types use the same names across plans; five review-focus conditions have named owning tests. Exact dependency versions and conversion capability decisions are intentionally outputs of M1, rather than unmeasured claims here. No material product decision needs to reopen the approved design.

Stop here for the present request. When Josh authorizes execution, start M1 task 1; use the inline execution method already selected in `IMPLEMENTATION_PROMPT.md`.
