# Review comment outcomes — 2026-11-12

Starting point: clean ukulele-songbook worktree at 119535e. Original main checkout
and all its untracked files were preserved. No deployment, publication, push,
GitHub CI, provider request or collection transmission was performed.

| Review comment | Investigation and outcome |
| --- | --- |
| Overall styling | Player controls had browser-default styling; workspace styling did not cover editor, setlists or print well. Added consistent cream/green surfaces, control borders, focus states, spacing and responsive layouts. Visual acceptance remains subjective. |
| Minus/value/plus control | Existing transpose/capo inputs lacked steps. Added bounded, labeled minus/plus buttons; retained numeric input for direct keyboard entry. |
| A− / A+ | Added bounded text-size buttons alongside direct range control. |
| High G / Low G | Existing code already changes open G from MIDI 67 to 55. Most fingerings remain identical because pitch classes match; slash-bass validation can differ. Kept the setting with explanatory help rather than claiming it transposes the chord. |
| Shape/sounding key clutter | Moved key reporting into capo help; source and performance semantics remain intact. |
| Ukutabs control reference | Adopted compact grouped step controls and fewer exposed export actions; did not browse or transmit collection data. |
| Edit source layout | Screenshot confirmed inline label/textarea baseline alignment. Added full-width monospaced source editor and desktop side-by-side music preview, with stacked narrow layout. |
| Hover chord shapes | Added hover/focus chord diagrams in playing music, using current tuning and validated custom definitions. Print excludes popovers. |
| Print styling / pixelated preview | Endpoint rendered at 100 dpi. Browser regression measured 850px Letter preview; increased to 200 dpi (1700px). PDF artifact remains vector; preview stays a raster, so extreme zoom can still pixelate. Added framed preview surface and grouped print controls. |
| Export ChordPro says online only | Export job control and offline status were adjacent but independent. The code did not use “Online only” as an export error. Export now starts the file download on completion and retains a retry link; exports are grouped in a menu, offline status stays visible separately. |
| Export/download menus and automatic offline storage | Added offline options menu. First online viewing automatically stages a verified song and shell, reporting success/failure. Existing selections are retained to preserve optional originals and stale copies; explicit refresh/retry/removal remains available. Browser eviction and failed caching remain possible. |
| Setlist styling | Added styled forms, song cards, ordered occurrence controls and print controls. |
| F# and all chord representations | Built-in table contained only seven chords. Added deterministic bounded voicing search, checking complete pitch-class set, span and requested bass. Regression covers 17 enharmonic root spellings × 11 qualities, including F#. Supported qualities: major, minor, 7, m7, maj7, dim, aug, sus2, sus4, 6, m6. Arbitrary extended/altered chords and impossible four-string bass voicings remain explicitly unavailable; displaying an invented diagram would be incorrect. Custom definitions retain validation. Search gives pitch-valid candidates, not a guarantee of ergonomic fingering. |

Evidence and limits: synthetic fixtures only. PDF extraction drafts remain
review-only. Detailed per-page error counts, correction times, live vision
fidelity, visual inspection of real-song PDF raster pages and physical-phone
checks remain unverified. Viewport emulation is not a physical device test.
The old port-8000 demo did not respond from the sandbox; it was not restarted
or treated as the verification instance. Disposable test servers were used.

Verification actually run:

- `uv run --offline pytest -q`: 206 passed, one existing Starlette warning.
- Final affected `pytest tests/integration/test_pdf_jobs.py -q`: 6 passed,
  same warning, after preview resolution change.
- `npm test --workspaces --if-present`: 5 web + 25 music passed.
- `npm exec playwright test`: final 85 passed (27.0s), Chromium; earlier
  failing runs exposed menu-test synchronization, shared preferences and the
  editor alignment finding, all corrected before final run.
- `npm run typecheck`, `npm run build`, generated API schema check,
  Ruff check/format and `git diff --check`: passed.
- Inspected synthetic player and corrected desktop editor screenshots locally;
  ignored screenshots remain in `.local/review/` and are not committed.

Final review was performed inline by the author, as requested; it is weaker
than independent review. The editor's tall preview initially stretched grid
rows and overflowed a wide tab. Its new alignment regression failed at a
290px offset, then passed after separating the two columns and constraining
preview scrolling. Final full browser suite is green. No other critical or
important finding remained in the reviewed task diff. Unsupported voicings,
manual refresh of existing offline selections, raster zoom limits and the
previously recorded corpus/device/provider limitations remain as described.
