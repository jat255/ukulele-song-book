# Second review: controls and navigation
Base: 749457e. Inline execution; no delegation or routine check-ins, as requested.
Design: retain the compact right controls panel, reorganized into Key & capo,
Readability, and Practice cards. Put transpose/capo together, text size next to
spacing/columns, and scrolling next to speed/section/wake controls. Chords move
to a collapsible overview above music. Phone tools remain a dismissible overlay.
Library actions use native popovers with Escape/outside-click dismissal and
viewport-bounded positioning; opening a menu never changes row geometry.
Settings use labeled Playing and Printing default fieldsets with responsive
spacing. Player/Print without IDs show explicit destination-specific song choosers.
Verify regression RED→GREEN, existing suites, screenshots at desktop/phone,
then inline final review, commit task-owned paths and rebuild the existing local demo.

Follow-up: keep capo readable at narrow widths, remove high/low-G UI, fix clipped
chord hints via a viewport-positioned portal, and correctly include non-triad
slash bass notes in voicing validation. Preserve existing serialized tuning
fields for compatibility; do not fabricate unplayable four-string chord shapes.
