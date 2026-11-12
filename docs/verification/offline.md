# Offline and reconnection verification

Local automated checks use synthetic songs and a disposable local server. The
Chromium and WebKit tests exercise authenticated download, cold offline open,
transposition, repeated setlist occurrences, changes and deletions on the
server, explicit refresh, partial cache damage, preference reconciliation and
logout removal. Individual test cases and commands are in the implementation
plan and `tests/e2e/offline-*.spec.ts`.

The tested local browser versions were Chromium 158.0.8127.18 and Playwright
WebKit 27.2. The WebKit reconnection suite uses isolated persistent profiles:
in this environment a transient WebKit test context lost a synthetic Cache
Storage entry on ordinary online navigation, while a persistent profile retained
it. Private-browsing behavior is not established by these tests.

No actual phone or physical-device airplane-mode run was available. Viewport
emulation does not establish physical-device layout, scrolling, app lifecycle,
storage eviction or wake-lock behavior. Real-song PDF raster pages have not
been visually inspected; automated text, page-size and font checks do not prove
the absence of visual clipping. PDF extraction remains review-only. Detailed
per-page error counts and correction times are unmeasured, and live vision
fidelity remains unverified.

Preference reconciliation chooses the greater `(updatedAtMs, deviceId)` tuple
for each independent group. Timestamps are generated on each device and are
not a globally accurate clock. A device with an incorrect clock can therefore
win or lose against a later real-world change. Existing server envelopes remain
in seconds and are converted to integer milliseconds at the client boundary.
Canonical source editing is not queued offline and continues to use revision
conflicts.

Downloaded sets created before ordered-set payload hashes were introduced need
to be downloaded again. Setlists deleted before tombstone migration may be
reported as unavailable rather than definitively deleted. Neither condition
causes a local copy to be silently overwritten.

Local runs on 2026-11-11 passed the full 81-test Chromium browser suite and all
19 synchronization tests in isolated persistent WebKit profiles. The Python
suite passed 171 tests with one Starlette deprecation warning. The WebKit run
is an engine-level local test, not an iOS Safari or physical-phone test.
