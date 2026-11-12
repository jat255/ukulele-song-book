# AI conversion configuration
Base 279c555, ukulele-songbook; work inline with no delegation.

Settings opens an accessible modal for one active conversion service: display
name, Anthropic/OpenAI-compatible protocol, base URL, vision model, optional API
key (replace/retain/remove), and enabled flag. Preserve explicit per-import page
submission consent. NVIDIA preset fills https://integrate.api.nvidia.com/v1;
model is user-supplied, and no free-tier/quota/model capability promise is made.
Connection test is explicit and sends only a synthetic image, never library
content. Saving never contacts a provider. No live requests during development.

Implement test-first in these stages:
1. Server-owned configuration persistence with authenticated/CSRF routes,
   revision conflicts, masked credentials, restrictive file permissions and
   atomic writes. Separate credentials from portable exports; document backup
   recovery. Avoid promising encryption unless an actual encryption boundary
   and key lifecycle are implemented.
2. Provider factory shared by status/API/worker, hot reloaded for new jobs.
   OpenAI-compatible image chat adapter; bounded requests, no redirects/key
   forwarding, validated URL, explicit disabled state, structured-response
   validation and sanitized errors. Freeze provider identity/config revision
   into authorization so queued pages never move to a changed endpoint.
3. Dialog, provider presets/custom model, saved-key indication, save/cancel,
   explicit connection test with synthetic payload disclosure and visible errors.
   Update import consent to identify selected service and model.
4. Mock-transport tests for vision payloads, malformed/truncated/unauthorized
   responses and endpoint changes; API/auth/credential/portability tests;
   dialog keyboard/error/persistence tests. Full Python/JS/browser gates,
   screenshots, inline final review, task-only commit and local demo rebuild.

Limits: no collection transmission, paid calls, live-provider capability claim,
CI/push/publication or remote deployment. Preserve existing checkouts and data.
Reference: NVIDIA NIM multimodal docs confirm OpenAI-compatible chat completion
image content; model-specific support and current account allowances remain
unverified. This is a new multi-layer feature, not a UI-only settings patch.
