# Chord placement prompting and fresh import attempts
Base bb9a3a3 on ukulele-songbook. Inline, no live provider calls or collection transmission.
Authority: approved songbook design and current user feedback about placement and clearing drafts.
1. Share a stronger transcription contract across Anthropic and compatible providers: page/column reading order, exact character/syllable anchoring, authored inline examples, lyric-preserving checks and explicit uncertain-placement fallback. Mock-only payload tests; no claimed live-fidelity improvement.
2. Transactionally discard pending drafts with expected state/revisions. Reject active workers, concurrent edits/acceptance and accepted-only attempts. Preserve original files and accepted provenance/songs; remove only unaccepted drafts/provenance and empty attempts.
3. Import queue Discard attempt and Start over. Start over reuses the managed source and only unaccepted selections; keeps exact page/crop selections until edited; requires fresh explicit AI consent before submission. No automatic conversion request on clearing/preparing.
4. Focused RED→GREEN tests, full Python/JS/browser checks, schema/lint/build, inline review, task-owned commit and local demo rebuild. Retain runtime provider settings.
