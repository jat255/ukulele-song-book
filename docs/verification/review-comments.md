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

## Second review — controls and navigation

- Library Export and Offline options now use native floating popovers with
  Escape and outside-click dismissal. They do not expand the song row. Phone
  bounds are checked at 390 × 600; action panels scroll within a bounded height.
- Chord diagrams moved from the bottom of the tools drawer to a horizontal
  overview above the music, with Show/Hide chords. Hiding/revealing them pauses
  auto-scroll because it changes layout. Individual chord hover diagrams remain.
- Settings now groups Playing and Printing defaults into separate labeled cards,
  with vertical labels and consistent field spacing; cards stack on narrow screens.
- `/player` and `/print` without a song ID now show distinct searchable song
  choosers. Their links open that destination for the selected arrangement.
  Arrangement editor/print navigation retains the selected song.
- The tools panel now has Key & capo, Readability, and Practice cards. Key/capo,
  text/density/columns, and scroll/section/wake controls are grouped by purpose.
  Scrolling is the prominent practice action; variant saving and cache status
  are secondary. The desktop panel stays in view while music scrolls; phones
  retain a dismissible overlay with focus management.

Native popovers were chosen for built-in keyboard/light-dismiss behavior.
Synthetic desktop and phone screenshots were visually inspected. Phone tests
remain viewport emulation; prior real-corpus, PDF and live-provider limits are
unchanged. No collection data was sent externally.

Final second-review checks: full Chromium suite 87 passed (27.3s), web/music
unit suite 5 +25 passed, typecheck and production build passed, whitespace
check passed. Final inline review found a setlist-ID navigation edge case;
the regression failed before the guard and passed afterward. Original browser
fixtures were adjusted to open popovers through their real buttons. No Python
code changed in this follow-up; the previously recorded Python results belong
to the earlier review, not a new backend verification claim.
Focused WebKit verification of the new chooser, controls, chord toggle, popover
geometry/dismissal and contextual navigation: 2 passed (4.6s). This is not a
full WebKit/offline suite or a Firefox/physical-phone claim.

## Capo, tuning removal and chord hints

- Reproduced the capo field at 24.5px wide. It now spans a full control row;
  redundant native spinners are hidden while numeric keyboard input remains.
  The regression checks a two-digit value at 1440, 390 and 320px widths.
- Removed High G / Low G controls and help from player and default settings.
  Existing serialized tuning data remains readable for compatibility.
- Reproduced clipping with a short synthetic song: hit-testing the lower part
  of the visible-looking hint hit the page instead. Hints now render in a body
  portal with fixed positioning and viewport collision handling. Hover, focus,
  Escape, and pointer movement into the hint are covered; scroll/resize dismiss.
- Slash-bass validation incorrectly excluded bass notes outside the named triad.
  It now includes that note and requires it to be the lowest sounding pitch.
  Unit tests verify complete pitch sets and bass for Am/D, C/D and G/B and reject
  an authored Am shape mislabeled Am/D. No simplified or guessed bass diagram
  is substituted when an exact four-string voicing is unavailable.
Final follow-up verification: Chromium 89 passed (28.1s), focused WebKit 4
passed (5.7s), web/music unit suites 5 +26 passed, typecheck/build and diff
whitespace checks passed. A resize/refocus assertion initially raced deliberate
hint dismissal; corrected the test sequence, then reran the whole Chromium
suite. Visually inspected the synthetic unclipped hint and Am/D overview.
Final inline review found no remaining critical/important task finding.
Existing physical-phone, Firefox, real-PDF and live-provider limits remain.

## Sign-in styling

The unauthenticated and loading branches bypassed the workspace class, so
workspace styles never applied. They now use the shared cream/green theme with
a centered responsive card, vertically spaced password form, prominent submit
button, visible focus styles and inline error feedback associated with the field.
The regression failed against the bare page before implementation. Coverage
includes 1280/390/320px card bounds and wrong-password feedback/field clearing.
Sign-in final verification: full Chromium 90 passed (28.3s), focused WebKit
2 passed (4.9s), units 5+26 passed, typecheck/build/diff checks passed. Desktop
and phone synthetic error-state screenshots visually inspected. Inline review
found no remaining task issue. Physical-phone/Firefox and prior corpus/PDF/
provider limits remain unchanged.
