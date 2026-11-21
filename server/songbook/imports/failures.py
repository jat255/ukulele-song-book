"""Whitelisted failure feedback; never serialize provider text or exception messages."""

DETAILS = {
    "codex_empty_draft": (
        "Codex returned an empty draft.",
        "Open the Codex conversation and logs to see the model's explanation.",
        False,
    ),
    "codex_turn_failed": ("The Codex turn failed before completing.", "Open the Codex conversation and logs for details, then retry if appropriate.", True),
    "codex_auth": (
        "Codex is not signed in or the account cannot be used.",
        "Sign in to Codex in Settings and start over.",
        False,
    ),
    "codex_rate_limit": (
        "The Codex usage limit was reached.",
        "Check Codex usage in Settings and retry when capacity is available.",
        True,
    ),
    "codex_network": (
        "Codex could not connect to its service.",
        "Check the network connection and retry.",
        True,
    ),
    "provider_auth": (
        "AI service rejected the API credentials.",
        "Check the saved API key and account access in Settings, then start over.",
        False,
    ),
    "provider_rate_limit": (
        "AI service rate limit or quota was reached.",
        "Wait and check provider credits or limits before retrying.",
        True,
    ),
    "provider_model_or_endpoint": (
        "AI endpoint or model was not found.",
        "Check the base URL and exact vision model ID in Settings, then start over.",
        False,
    ),
    "provider_request_invalid": (
        "AI service rejected the conversion request.",
        "Check model image support and endpoint compatibility; try fewer pages.",
        False,
    ),
    "provider_request_too_large": (
        "AI service rejected the request as too large.",
        "Choose fewer pages or a service with a larger image/context limit.",
        False,
    ),
    "provider_unavailable": (
        "AI service is temporarily unavailable.",
        "Wait before retrying; check the provider service status.",
        True,
    ),
    "provider_timeout": (
        "AI service did not respond within the request timeout.",
        "Wait or try fewer pages before retrying.",
        True,
    ),
    "provider_network": (
        "The server could not connect to the AI service.",
        "Check the endpoint, network and TLS configuration.",
        True,
    ),
    "provider_redirect": (
        "AI endpoint returned a redirect, which was not followed.",
        "Use the final API base URL in Settings; credentials are not forwarded.",
        False,
    ),
    "provider_output_truncated": (
        "AI output stopped at the output-token limit.",
        "Try fewer pages so the complete ChordPro draft fits in one response.",
        False,
    ),
    "provider_invalid_response": (
        "AI service returned an invalid or incomplete draft response.",
        "The model must return JSON with source and uncertainties; try fewer pages or another vision model.",
        False,
    ),
    "provider_refused": (
        "AI service refused or filtered the conversion.",
        "Check whether the selected content is supported by your service.",
        False,
    ),
    "provider_changed": (
        "AI service settings changed after this attempt was authorized.",
        "Start over and authorize the current service and model.",
        False,
    ),
    "provider_not_configured": (
        "The worker has no enabled AI conversion service.",
        "Configure and enable a service in Settings, then start over.",
        False,
    ),
    "source_unavailable": (
        "The managed source could not be read or validated.",
        "Check the original file; re-upload it if necessary.",
        False,
    ),
    "local_pdf_failed": (
        "Local PDF text extraction failed.",
        "Check that the original opens and is not password-protected; try custom pages or AI conversion.",
        True,
    ),
    "ai_pdf_failed": (
        "PDF pages could not be prepared for AI conversion.",
        "Check the original PDF, selected pages and page/image limits.",
        False,
    ),
    "draft_invalid": (
        "The returned draft could not be processed as ChordPro.",
        "Try fewer pages or another vision model; the original is retained.",
        False,
    ),
    "retries_exhausted": (
        "The attempt was interrupted or reached its retry limit.",
        "Start over to create a fresh attempt with new authorization.",
        False,
    ),
    "restore_requires_review": (
        "This attempt requires review after a library restore.",
        "Start over to create a new conversion attempt.",
        False,
    ),
    "conversion_failed": (
        "Conversion failed; no specific cause was recorded.",
        "Older attempts cannot reveal their original cause. Start over for detailed feedback from the updated worker.",
        False,
    ),
}


def details(code):
    message, hint, retryable = DETAILS.get(code, DETAILS["conversion_failed"])
    return {"message": message, "hint": hint, "retryable": retryable}


class ConversionFailure(ValueError):
    def __init__(self, code):
        self.code = code if code in DETAILS else "conversion_failed"
        super().__init__("Vision conversion failed: " + details(self.code)["message"])


def http_failure(status):
    if status in (401, 403):
        return "provider_auth"
    if status == 429:
        return "provider_rate_limit"
    if status == 404:
        return "provider_model_or_endpoint"
    if status == 413:
        return "provider_request_too_large"
    if 300 <= status < 400:
        return "provider_redirect"
    if status >= 500:
        return "provider_unavailable"
    return "provider_request_invalid"
