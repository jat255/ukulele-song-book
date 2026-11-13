# Library deletion, full-PDF default and conversion feedback
Base a7828ca, ukulele-songbook. Inline; no live provider requests or collection transmission.
1. Confirmed removal from library for arrangements and source-only entries.
   Preserve originals/revisions/import history; reuse arrangement tombstones and
   add revisioned source visibility metadata. Preserve source visibility on export/
   restore. Hide locally deleted cached entries within their browser/library scope.
2. Default a fresh PDF import to one song spanning the entire file. Count pages
   in an isolated bounded subprocess, expand explicit ordered pages, preserve
   crop semantics and selection limits (local20/AI5). Never truncate silently.
   Keep optional custom page grouping and retry's retained explicit selections.
3. Persist only whitelisted conversion failure codes and map to actionable public
   feedback. Distinguish provider auth/rate-limit/timeout/invalid request/response/
   truncation, changed configuration and local source/PDF failures. Preserve codes
   through AI service and worker, never provider response bodies/credentials/lyrics.
4. Test-first regressions, full suites, schema/lint/build, visual checks, inline
   final review, task-only commit and rebuild existing local demo with data and
   provider settings unchanged. Historical generic errors cannot be reconstructed.
