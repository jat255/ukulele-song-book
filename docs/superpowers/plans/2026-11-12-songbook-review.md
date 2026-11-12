# Songbook review follow-up
Base: 119535e, ukulele-songbook. Execute inline; preserve all existing checkouts.
Authority: approved songbook design and the user's tab-app-review.md comments.
1. Reproduce sparse layouts, control ergonomics, missing diagrams, preview resolution and export/offline behavior.
2. Add regression coverage, implement bounded controls, hover diagrams, desktop editor, consistent workspace/player/setlist/print styling, automatic verified song caching and export menus/downloads.
3. Run unit, Python, browser, typecheck/build and lint gates. Review the diff inline, track each comment and limitations in docs/verification/review-comments.md, then commit task-owned paths.
Rulings: retain explicit offline retries/refresh and optional originals; automatic viewing must not replace an existing selection or discard originals. Unsupported or impossible voicings remain explicit rather than fabricated. No provider, publishing, CI or deployment work.
