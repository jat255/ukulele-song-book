# Online songbook verification

The player was checked locally in Chromium at 1440×900, 390×844 and a 320×700
stress viewport. On a private ChordPro corpus arrangement, automated checks
found 69 rendered blocks and no document-level horizontal overflow at each
viewport. Screenshots are kept under ignored `.local/evidence/`; this check does
not establish that every glyph or chord anchor is visually correct. The sample
contained no tab blocks.

A synthetic fixture with 30 ordered lines and a wide four-string tab was checked
in the browser. The desktop layout preserved line order and kept section
headings with following content. At 320px, 32px requested text remained 32px,
manual three-column selection reported a one-column width limit, and the wide
tab could scroll horizontally. The test uses Chromium viewport emulation; a
physical phone and its browser have not been checked.

These checks do not change the M1 finding that PDF extraction drafts require
manual review. Live vision conversion fidelity remains unverified.
