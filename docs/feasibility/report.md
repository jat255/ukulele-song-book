# Rendering and conversion feasibility

This is a preliminary report, not milestone sign-off. The sources are a small private sample; results do not establish collection-wide accuracy. All original files and rendered evidence remain in ignored local storage. PDF conversion drafts are never automatically accepted.

## Tooling and measurements

The local checks used Python 3.12.3, Node 26.13.0, pytest 9.2.0, Ruff 0.17.4, pdfplumber 0.11.10, pypdfium2 5.15.2, pypdf 7.0.1, Python Playwright 1.65.0 and its Chromium 158.0.8127.18. React, Vite and npm test dependencies are pinned in `package-lock.json`. Independent rendering used the installed ChordPro application bundle 6.090.1; its `--version` command returned no text. Noto Serif regular SHA-256 is `c8f669ceb2c9c60ccf55198b305e08a997ffca79a38cc7eeb551e643cbe66505`; Noto Sans Mono regular is `d9e2b23d19f8230be7146f409a52b1d23117e635e28f2e2892cf91b7382f325b`. Font licenses are bundled alongside the files.

The private source manifest records source hashes, one-based pages, selection categories and observations. The three existing ChordPro sources round-tripped byte-identically. Their independently rendered PDFs and shared-renderer PDFs were inspected locally; each shared output had two pages. One source required correction of adjacent chord spacing during evaluation. Rendered tab alignment appears intact on the selected tab sample. The renderer does not yet draw chord diagrams or apply performance transformations. A normalized-word check found 25, 22 and 5 unmatched word occurrences for c1, c2 and c3 respectively. Of those, 16, 20 and 4 had an internal chord anchor, so extracting PDF text can split a word around chord labels. Comparing at chord-fragment boundaries initially left 7, 2 and 0 unmatched fragments. Unicode normalization resolved all remaining mismatches: the font encodes some letter pairs as ligatures. After normalization, all lyric-fragment token occurrences were present for these three samples. This comparison does not itself prove visual chord placement or line order.

PDF extraction results and failures are described in [conversion-results.md](conversion-results.md). The selection covers ordinary, two-column, mixed-tab, vector-heavy and multi-song PDFs. The vector-heavy sample is materially incomplete and a two-column draft interleaved content; both require manual review against the original. The book sample requires separate regions and its draft did not preserve inline chords correctly. Missing/extra line counts, wrong-anchor counts and correction times are not fully measured. The provider was not called and live AI fidelity is unverified.

## Working decision and unresolved gate

The source-preserving TypeScript lexer, pdfplumber coordinates, pypdfium2 rasterization and Chromium PDF output are the current candidates. They have not passed the complete milestone gate. Existing synthetic tests cover paper sizes, repeats, tab groups, overflow rejection, text size, column selection by actual PDF page count and chord anchors at narrow widths. CSS fragmentation and content order need broader checks; no claim is made that every source is paginated correctly. Do not treat the current draft converter as accurate automatic transcription. A page-by-page comparison, accurate review effort measurements, and detailed verification of chord placement and line order remain required before milestone sign-off.

Useful local commands (set `PLAYWRIGHT_BROWSERS_PATH` if browsers were installed outside Playwright's default cache):

```sh
npm test --workspace @songbook/music
npm run build
npm exec playwright test tests/e2e/feasibility.spec.ts
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python tools/convert_corpus.py --manifest .local/corpus/manifest.json --output .local/evidence/conversion
uv run python tools/render_corpus.py --manifest .local/corpus/manifest.json --output .local/evidence/shared
```
