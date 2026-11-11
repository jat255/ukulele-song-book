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

Performance checks on one private ChordPro corpus sample confirmed that its
canonical UTF-8 hash remained unchanged after display transposition, capo
selection and diagram lookup. Synthetic browser checks covered a 5px/s scroll,
manual and layout-change pause, restored preferences, denied wake lock,
transposed adjacent chords at 320px, and an explicit variant that retains tab.
The built-in ukulele shape dictionary is intentionally small; unvalidated shapes
are shown as unknown. Tab is not transposed. Live physical-device behavior
remains unverified.

Three private ChordPro corpus samples were rendered at 12pt to Letter and A4;
only anonymous sample numbers and aggregate counts are recorded here. The
resulting PDFs and 100dpi raster pages remain in ignored local evidence storage.
A normalized extracted-text check found all lyric segments of at least four
characters, counting repetitions: sample 1, 124/124 on both papers; sample 2,
94/94 on both; sample 3, 132/132 on both. The four tab lines in sample 2 were
found exactly in extracted text on both papers. These automated checks do not
prove visual alignment, absence of clipping, or correctness of short fragments.
The rasterized pages have not been visually inspected.

| Sample | Letter pages / columns | A4 pages / columns | Tab blocks | Embedded font programs |
| --- | --- | --- | --- | --- |
| 1 | 2 / 2 | 2 / 2 | 0 | 3 |
| 2 | 2 / 2 | 2 / 2 | 1 | 4 |
| 3 | 2 / 1 | 2 / 1 | 0 | 3 |

Font checks counted embedded font files and embedded Type 3 character
programs; no unembedded font descriptors were found in these six artifacts.
An earlier set of blank artifacts exposed a global print-style collision and is
superseded by the evidence above. The integration test now checks actual PDF
text after the print workspace is present.

The sample 2 page and text counts were rechecked after the tab-group pagination
fix. Its earlier raster images predate that fix; updated PDF artifacts were
retained privately but their pages have not yet been rasterized or inspected.
