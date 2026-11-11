# Personal ukulele songbook — approved design

Approved by Josh on 2026-11-11, including embedded text tablature support and PDF/ChordPro-only imports.

## Intent

Build a private, self-hosted web app for Josh's collection of ukulele chords and tabs. It should make songs easy to find, play from a laptop or phone, transpose, and print consistently. Song content must remain useful outside the app.

**Information density is the primary layout requirement.** Use vertical space for music, place playing controls in a right sidebar, and use multiple columns when width permits. Printed output should minimize pages while respecting the user's chosen readable text size.

This document describes the approved product and boundaries. It is not approval to deploy or a detailed implementation plan.

## Confirmed decisions

- Primary devices: laptop and phone.
- Private hosting on Josh's infrastructure, accessible away from home.
- Server-managed library, with downloaded songs available for offline playing. Editing requires a connection initially.
- ChordPro is the authoritative editable song format. The original PDFs remain preserved attachments.
- Chord transposition is in scope. Tablature transposition is deferred.
- Playing tools and diagrams belong in a tall right sidebar. On phones, use a collapsible right panel.
- Compact spacing and automatic columns on wide screens are the default. Text size, density, and columns are separately adjustable.
- Print has its own density, text size, column, margin, and diagram controls. It shares the arrangement and selected performance key with playing.
- An optional external AI service may receive selected PDF pages to draft an arrangement. The user reviews the result before accepting it.

## Existing material and evidence

The workspace initially contained no application code or git repository. A read-only inventory of the supplied NAS directory found 116 PDFs, three `.chordpro` files, and two `.cho` files among the supported formats, excluding hidden files. There are also multi-song PDF books and apparent alternate versions.

Samples demonstrate chord-and-lyric sheets, two-column layouts, tablature, and custom chord shapes. Some PDFs yield useful text; another sampled PDF yielded chord labels but little other content and contained no embedded images. Consequently, missing extracted text cannot be treated as proof of a scanned document: rendering a page for visual recognition may be needed for vector content too. No collection-wide conversion accuracy has been measured.

The existing Rocky Mountain High ChordPro file includes sections, custom chord definitions, a key directive, and capo information. Import must preserve these semantics rather than reducing everything to plain lyric text.

The interactive layout study has been reviewed in conversation. Its latest screen is `.superpowers/brainstorm/97691-1794378900/content/songbook-print-density-v5.html`. These ignored files are exploratory artifacts, not product code. Preserve stable screenshots with implementation documentation if needed.

Browser checks exercised desktop columns, density settings, focus view, chord changes, auto-scroll, phone controls, a 390px viewport, and print controls. A generated sample PDF decreased from two pages to one at the same text size; Letter and A4 versions contained all sample sections. This validates the example layout, not real-song conversion or production pagination.

## Approaches considered

1. **Server-managed files with offline playing — selected.** One server owns the library; devices download songs or setlists. Central backups and straightforward edits fit the intended personal app. Offline edits are deferred.
2. **Fully offline editing with later synchronization — deferred.** Each device could edit independently, but resolving conflicting arrangements and file changes adds complexity without serving a confirmed initial need.

A PDF-only viewer would support the originals but would not supply reliable transposition, reflow, or consistent printing. It remains a fallback view inside the selected approach rather than the main content model.

## Proposed technical foundation

These are recommendations from the assistant, not technical choices Josh has separately approved:

- A responsive, installable web app with a browser cache for selected offline content.
- A TypeScript/React client for the library, song renderer, editing, and print controls.
- A Python API and a background import worker for PDF extraction, page rendering, optional AI conversion, and PDF generation.
- SQLite for the initial personal library's index, settings, job status, and setlists; a server-owned directory for ChordPro and source files. No distributed database is needed initially.
- A browser-based rendering path shared by preview and server-generated PDFs. The server's PDF generator should use a controlled headless browser environment for repeatable pagination.
- Container deployment, ideally with a declarative service definition, persistent volumes, and an HTTPS reverse proxy.

Exact framework packages, supported ChordPro parser, PDF tools, AI provider/model, and pinned versions belong in the implementation plan after a conversion and rendering feasibility milestone. If suitable parser behavior is incomplete, document the supported subset and retain all unsupported source content.

The hosting machine, hostname, and existing identity provider are deployment configuration decisions. The app should not require a particular hosting vendor or a direct NAS connection from the browser.

## Portable storage and ownership

One song can have multiple arrangements. An arrangement is the unit of editing, transposition, performance preferences, and print output. Keep stable IDs independent of titles and filenames.

Example server-managed layout:

```text
library/
  arrangements/<arrangement-id>/song.chordpro
  arrangements/<arrangement-id>/attachments/<attachment-id>.pdf
  arrangements/<arrangement-id>/revisions/...
  sources/<source-id>/original.pdf
  app.sqlite
```

The exact directory structure is a builder choice. Shared sources, especially songbooks, should be referenced rather than copied once per extracted song.

- ChordPro is authoritative for lyrics, chord positions, title/artist, sections, musical metadata, tablature blocks, comments, and custom chord definitions.
- A parsed internal representation is a derivative for rendering and searching; JSON in the database must not become a competing authoritative song format.
- Preserve unsupported directives and original source text on round trips. Flag unsupported rendering behavior; do not silently delete content or interpret unknown directives as executable markup.
- Use broadly supported ChordPro constructs for new content. Export valid standalone `.chordpro` files, including custom chord definitions required by the arrangement.
- App-specific preferences, favorites, setlists, provenance, and attachment relationships live outside the ChordPro content. Provide a documented, versioned JSON export alongside the song files and attachments.
- Retain accepted revisions so a bad edit or conversion can be undone. An edit must not leave file content and its database index disagreeing after a crash.
- Treat the app directory as server-managed. Direct filesystem editing and bidirectional NAS synchronization are not supported initially; external changes arrive through explicit import or replacement with conflict review.

Provide both arrangement-level export and a complete portable library export. A backup includes canonical files, attachments, revisions, configuration, and database state. Restore must be tested, not assumed from file copying alone.

## Library and navigation

Search title, artist, lyrics, tags, and chord names. Offer favorites, recently played songs, arrangement variants, and ordered setlists. Provide a source-PDF fallback for every imported arrangement and for documents that have not yet been converted.

Opening a song should resume that arrangement's preferred key, capo, text size, density, column preference, and auto-scroll speed. Do not resume scrolling automatically. Setlist order supports next/previous song navigation with minimal interruption.

The playing view hides persistent library navigation until requested. Search, editing, and import management can use conventional workspace layouts; the density requirement is strongest while playing and printing.

## Import and correction

Support PDF upload, ChordPro upload, and an explicit scan of a server-visible source folder. Supported import formats are PDF and ChordPro (`.chordpro` and `.cho`); folder scans ignore other file types. The supplied NAS path is local configuration, not a hard-coded application path. Mount it read-only if used directly. Copy imported originals into managed storage so existing songs remain usable when the NAS is unavailable.

The initial import pipeline is:

1. Register the original, hash it, and check for exact duplicates. Similar titles trigger a review suggestion, not automatic merging. Ignore operating-system metadata sidecars.
2. Import ChordPro directly, preserving directives and validating renderability. Existing ChordPro paired with a PDF takes precedence over regenerating the same arrangement from that PDF.
3. For PDFs, extract text with positional information, identify reading order and song boundaries, and produce a draft. Handle two-column source layouts before guessing chord-to-lyric alignment.
4. When extraction is incomplete, offer page rendering and optional external AI-assisted conversion. Send only the selected document/pages after a clear user action; never silently upload the whole collection. Provider credentials remain on the server. Report provider errors and retryable job failures.
5. Review the original page next to editable ChordPro and a rendered preview. Flag uncertain chord placement, missing content, unsupported notation, metadata, and potentially inconsistent capo/key information. AI output is always a draft; it must not fabricate missing verses or replace uncertain chords without review.
6. Accept the reviewed arrangement into the library. Keep import provenance and source page references. Retrying jobs must not duplicate accepted arrangements or overwrite later edits.

Jobs have visible queued, processing, needs-review, accepted, and failed states. They survive page navigation and server restart. Batch imports land in a review queue rather than requiring review to block processing of every later file.

For multi-song PDFs, allow selecting page ranges and manually identifying songs. Automatic segmentation may suggest boundaries but must not pretend a whole songbook is a single arrangement. A song spanning pages is a single arrangement with multiple source page references.

Text tablature is supported inline in the initial release using standard `{start_of_tab}` / `{end_of_tab}` blocks, interspersed with chord-and-lyric sections. Preserve whitespace and use a monospaced font. These blocks are literal content, including any chord names written inside them; do not transpose their contents. Label retained tab as unchanged when surrounding chords are transposed. Keep complete string groups together when paginating. If a block is too wide for a column, adapt column layout or offer horizontal scrolling on screen; do not wrap individual string lines and destroy alignment. Flag blocks that cannot fit the chosen print settings for review.

Where a PDF's graphical tablature cannot be converted faithfully to text, retain a page reference or user-selected image attachment rather than losing the notation. Such arrangements may require the original view for complete performance material in the initial release. Tablature conversion fidelity is part of the feasibility milestone; tablature transposition remains deferred.

## Playing and transposition

Use a compact title and place controls, navigation actions, status, and ukulele chord diagrams in the right sidebar. The song viewport receives the full available height. Focus view hides surrounding navigation; on phones, controls collapse into a slim right-side tab and overlay the song when opened.

Offer separate text size and density controls. Compact spacing is the default, with tighter and more relaxed alternatives. Reflow must retain chord-to-word relationships and avoid clipped or overlapping chord symbols, especially when adjacent chord names widen after transposition.

Automatic columns use the available music width and selected font size. Read down each column, then across. Preserve section order and keep sections together when feasible. A section too tall to fit may split between complete chord/lyric lines, with its heading retained with following content. Reduce column count if width becomes insufficient. Expose a manual preference and never shrink text silently to force more columns.

Transpose parsed chord roots and slash bass notes while retaining qualities and extensions. Handle sharps, flats, minor and extended chords, slash chords, no-chord markers, and unrecognized tokens explicitly. Prefer sensible enharmonic spelling for the selected key, with a user override if needed.

Distinguish source key, displayed chord shapes, capo fret, and sounding key. Changing capo alone changes the reported sounding key; changing the displayed key transposes chord shapes. Do not overwrite canonical source chords when changing performance settings. An explicit save-as-arrangement action can create a new source arrangement from a transposed version.

The import reviewer resolves inconsistent or missing key information rather than blindly trusting a PDF label. Derive ukulele diagrams from the displayed chords and selected tuning/voicing; never reuse a custom diagram under a new chord name without validating it. Unknown voicings are flagged rather than guessed. Standard GCEA is the initial tuning; support low-G as an explicit distinction where pitch-dependent behavior requires it. Guitar-source chord symbols may be useful, but guitar fingering diagrams are not ukulele diagrams.

Auto-scroll has start/pause, adjustable speed, and quick keyboard/touch access. Manual scrolling remains usable; stop at the song end and do not start after a layout change without user action. Offer section navigation and an optional keep-screen-awake feature where supported. Basic practice notes belong outside the canonical arrangement unless explicitly inserted as song comments.

## Dense printing and PDF output

Print the selected arrangement using the current performance key/capo, including a clear indication of chord shapes and sounding key. Rendering comes from the same parsed music as the screen view. Print layout settings remain independent of play settings.

Defaults follow the accepted study: compact spacing, narrow configurable margins, standard readable text size, compact header metadata, optional compact diagrams beside the header, and automatic one/two-column layout. Support Letter and A4 initially. Do not print application navigation or a decorative background.

The objective is to reduce page count without sacrificing chosen readability or losing content:

- Honor the chosen text size; provide density, margins, and columns before considering smaller text.
- Evaluate eligible column layouts at that size; prefer fewer pages. Resolve ties using readable line lengths and fewer awkward wraps. A manual column choice overrides automatic selection where feasible.
- Keep chord/lyric lines together. Keep headings with following lines and whole sections together when they fit. For oversized sections, permit line-boundary breaks rather than overflow or omitted text.
- Provide actual paginated preview and page count from the production PDF renderer before download. The mockup's full-size preview does not yet implement this production paginator.
- Export individual arrangements and ordered setlists. In setlist exports, default to a new song starting on a new page; optionally pack songs onto shared pages to minimize paper use. Never silently mix the two behaviors.
- Preserve repeated choruses and all musical content by default. Abbreviating repeats is an editorial action, not an automatic page-saving technique.

Browser printing is a convenience; a server-generated PDF is the repeatable export path. Both should respect the same layout settings. Font availability and font embedding must be controlled for reproducible output.

## Offline behavior and synchronization

Explicitly download a song or setlist, including its rendered content, required assets, and diagrams. Offer original PDF attachments as an optional download because they consume more space. Distinguish downloaded, outdated, and online-only states truthfully.

Cache the application shell after an online visit. Offline users can open downloaded arrangements, transpose, adjust local performance settings, and scroll. Editing canonical content, importing, and server-generated PDFs require a connection initially. A local browser print of an already downloaded arrangement may be available, with the same browser limitations as online browser printing.

On reconnection, refresh changed arrangement revisions and report deleted/unavailable songs. Cached content can remain available until explicitly removed, with a clear stale/deleted indicator. Performance preferences may update locally offline and reconcile with the server on reconnection; deterministic latest-write behavior is sufficient for the initial personal app. Reject concurrent source edits using revision checks rather than silently overwriting another browser's edit.

Browser storage can be evicted, so offline status must be verified from actual cached assets. Request persistent storage where supported and provide storage management and re-download controls. Offline use begins after a successful authenticated download; it is not an offline first-login promise. Logging out offers removal of downloaded private content.

## Hosting and access

Initial audience is Josh, with a single private library. Public sharing, collaborative editing, and separate users' libraries are out of scope. Use authenticated access over HTTPS; do not expose an unauthenticated PDF library on the internet. The exact existing identity solution is chosen during deployment planning.

The backend owns NAS access, AI credentials, import execution, PDF generation, and persistent storage. Constrain file access to configured roots, validate uploads, and treat imported content as data. Preserve durable jobs across restarts. Avoid logging full lyrics or credentials unnecessarily.

Provide health checks, bounded resource use for expensive imports/PDF exports, visible failure messages, and a documented backup/restore process. Deployment configuration must separate persistent content from replaceable containers. No deployment is part of this design-review step.

## Delivery order and acceptance

### 1. Prove conversion and portability

Choose a small representative corpus including existing ChordPro, ordinary chord sheets, two-column sources, mixed tab, vector-heavy pages, and a multi-song PDF. Measure actual extraction fidelity, review effort, retained source content, and round-trip preservation. Demonstrate optional AI conversion on selected pages. This milestone determines realistic conversion automation and parser/tool selection.

Acceptance: every sample retains an accessible original; accepted conversions preserve verified lyrics and chord placement; unsupported content is flagged; exported ChordPro can be inspected in an independent compatible renderer with any compatibility limits recorded.

### 2. Deliver a useful online songbook

Implement the managed library, source/PDF fallback, review queue, editing and revisions, search, variants, dense playing view, transpose/capo behavior, diagrams, auto-scroll, and individual-song PDF export. Validate dense layouts against real imported songs, not just the fictional mockup.

Acceptance: no silent source edits from performance controls; laptop and phone layouts are usable; narrow widths retain correct chord placement; representative Letter/A4 PDFs include every section without clipping and report their actual page count.

### 3. Add setlists and offline playing

Add ordered sets, preferences, downloaded arrangements and assets, stale-content indicators, and setlist PDF exports. Confirm behavior without a network connection on real target browsers and after server-side edits.

Acceptance: downloaded songs open and transpose offline; online-only songs are identified; source conflicts do not overwrite changes; setlist order matches play and export; export/backup and restore preserve files and app metadata.

### 4. Deploy privately and refine

Configure the chosen host, HTTPS access, authentication, storage, and backups. Verify remote laptop/phone access and restore into a clean instance. Improve import automation and layout heuristics using actual review outcomes.

Deferred improvements include offline source editing, tablature transposition, audio playback, advanced rhythm/metronome tools, pedal integration, collaborative libraries, and automatic arrangement simplification. These do not block the core design.

## Builder discretion and remaining planning work

The builder should choose specific packages, database schema, background-job mechanism, atomic-write approach, renderer interfaces, cache strategy, and test framework. Validate current official documentation before pinning dependencies. Keep the personal deployment simple; add services only for a demonstrated requirement.

The conversion feasibility milestone must settle supported ChordPro constructs, ambiguous import examples, external AI provider configuration and cost visibility, and PDF pagination strategy. Hosting details and auth integration can be resolved during deployment planning without changing the product design.

## Format references

- [ChordPro introduction](https://www.chordpro.org/chordpro/chordpro-introduction/)
- [ChordPro directives](https://www.chordpro.org/chordpro/chordpro-directives/)
- [ChordPro key directive](https://www.chordpro.org/chordpro/directives-key/)
- [ChordPro transpose directive](https://www.chordpro.org/chordpro/directives-transpose/)
- [ChordPro tablature sections](https://www.chordpro.org/chordpro/directives-env_tab/)

Use the documented format's semantics and preserve imported constructs whose rendering is not yet supported.
