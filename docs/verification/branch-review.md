# Whole-branch review

The inline review covered the branch from the original main-branch base through
M1, M2 and M3, including the previously deferred M2 whole-branch review. It
checked managed-file and revision recovery, authentication and origin/CSRF
boundaries, import authorization and review-only drafts, performance controls,
PDF snapshots, offline storage/synchronization, archive validation and restore,
local packaging, and the verification ledgers.

One issue found during review was fixed: the portable export catalog was
bounded only after it was constructed in memory. The catalog now stops reading
rows once its configured size limit is exceeded; a regression test and the
portability/recovery suite passed after the change.

The tracked branch contains synthetic ChordPro fixtures, bundled fonts and an
empty provider configuration example. No private corpus files, rendered
collection pages, credentials or machine-specific input-root paths were found
in the reviewed changes. Local synthetic container and browser evidence stays
ignored. No provider was contacted and GitHub CI was not accessed.

Known limitations are recorded in [rulings.md](rulings.md),
[online-songbook.md](online-songbook.md), [offline.md](offline.md), and
[the feasibility report](../feasibility/report.md). In particular, real-song
raster pages have not been visually inspected, phone checks are viewport
emulation rather than a physical device, detailed PDF correction/error counts
remain unmeasured, live vision fidelity is unverified, and PDF drafts remain
review-only. The local Docker configuration is not a deployment security
architecture. OS packages and base image tags are not immutable snapshots.
