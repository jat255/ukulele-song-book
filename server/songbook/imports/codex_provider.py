"""Codex SDK-backed vision adapter for reviewed imports."""

import json
import math
import re
import tempfile
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from openai_codex import ApprovalMode, CodexError, LocalImageInput, TextInput
from openai_codex._run import _collect_turn_result
from openai_codex.generated.v2_all import TurnStatus

from .codex_service import CodexService
from .failures import ConversionFailure
from .providers.base import ProviderStatus, VisionDraft, VisionRequest
from .providers.prompt import transcription_prompt


def redact_error(message: str) -> str:
    """Remove common credential forms from diagnostic error messages."""
    message = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [redacted]", message)
    message = re.sub(
        r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|token|secret|password|authorization|cookie)([\"'\s:=]+)[^\s,;\"']+",
        r"\1\2[redacted]",
        message,
    )
    message = re.sub(
        r"\bsk-[A-Za-z0-9_-]+|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_.-]+",
        "[redacted]",
        message,
    )
    message = re.sub(r"https?://[^\s]+", "[URL redacted]", message)
    return (
        message
        if len(message) <= 4000
        else message[:4000] + " [error detail truncated]"
    )


def failure_for(error: Exception, *, context: str = "") -> ConversionFailure:
    message = (str(error) + " " + context).lower()
    if any(
        term in message
        for term in (
            "rate limit",
            "rate_limit",
            "usage limit",
            "usage_limit",
            "usagelimitexceeded",
            "429",
        )
    ):
        return ConversionFailure("codex_rate_limit")
    if any(
        term in message
        for term in ("unauthorized", "401", "authentication", "not logged in")
    ):
        return ConversionFailure("codex_auth")
    if any(term in message for term in ("network", "connection", "timeout")):
        return ConversionFailure("codex_network")
    if isinstance(error, (RuntimeError, CodexError)):
        return ConversionFailure("codex_turn_failed")
    return ConversionFailure("provider_invalid_response")


class CodexVisionProvider:
    def __init__(self, service: CodexService, model: str, *, on_progress=None):
        self.service = service
        self.model = model
        self.on_progress = on_progress

    def status(self) -> ProviderStatus:
        try:
            status = self.service.status()
        except Exception as error:  # noqa: BLE001 - SDK details can contain private content
            if self.on_progress is not None:
                self.on_progress(
                    f"\n[Connection error] {type(error).__name__}: {redact_error(str(error))}\n"
                )
            raise failure_for(error) from None
        if not status["connected"]:
            if self.on_progress is not None:
                self.on_progress("\n[Connection error] Codex is not signed in.\n")
            raise ConversionFailure("codex_auth")
        available = status["connected"] and any(
            item["id"] == self.model for item in status["models"]
        )
        return ProviderStatus(available, "codex", self.model, page_limit=5)

    def convert(self, request: VisionRequest) -> VisionDraft:
        def snapshot():
            try:
                value = self.service.usage()
                return value if isinstance(value, dict) else {}
            except Exception:  # noqa: BLE001 - usage data must not block conversion
                return {}

        before = snapshot()
        started_at = time.time()
        try:
            result = self._convert(request)
        finally:
            after = snapshot()
            finished_at = time.time()
            quota = {}
            for key in ("primary", "secondary"):
                start, end = before.get(key), after.get(key)
                delta = None
                if isinstance(start, dict) and isinstance(end, dict):
                    first, last = start.get("used_percent"), end.get("used_percent")
                    if (
                        isinstance(first, (int, float))
                        and not isinstance(first, bool)
                        and isinstance(last, (int, float))
                        and not isinstance(last, bool)
                        and math.isfinite(first)
                        and math.isfinite(last)
                        and 0 <= first <= last <= 100
                        and start.get("resets_at") is not None
                        and isinstance(start.get("resets_at"), (int, float))
                        and not isinstance(start.get("resets_at"), bool)
                        and started_at < start["resets_at"]
                        and finished_at < start["resets_at"]
                        and start.get("resets_at") == end.get("resets_at")
                        and start.get("window_minutes") is not None
                        and start.get("window_minutes") == end.get("window_minutes")
                    ):
                        delta = round(last - first, 4)
                quota[key] = {
                    "delta_percent": delta,
                    "before_remaining": round(100 - first, 4)
                    if delta is not None
                    else None,
                    "after_remaining": round(100 - last, 4)
                    if delta is not None
                    else None,
                    "window_minutes": end.get("window_minutes")
                    if isinstance(end, dict)
                    else None,
                }
            if self.on_progress is not None:
                parts = [
                    f"{key}: {item['delta_percent']:g} percentage points"
                    if item["delta_percent"] is not None
                    else f"{key}: unavailable"
                    for key, item in quota.items()
                ]
                self.on_progress(
                    "\n[Quota estimate] "
                    + "; ".join(parts)
                    + ". Shared account activity and reporting delays can affect this comparison.\n"
                )
        return replace(result, quota_usage=quota)

    def _convert(self, request: VisionRequest) -> VisionDraft:
        if not self.status().available or not 1 <= len(request.pages) <= 5:
            raise ConversionFailure("provider_not_configured")
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["source", "uncertainties"],
            "properties": {
                "source": {"type": "string"},
                "uncertainties": {"type": "array", "items": {"type": "string"}},
            },
        }
        pending: list[str] = []
        pending_size = 0
        last_flush = time.monotonic()

        def flush() -> None:
            nonlocal pending_size, last_flush
            if self.on_progress is not None and pending:
                self.on_progress("".join(pending))
                pending.clear()
                pending_size = 0
                last_flush = time.monotonic()

        def log(message: str) -> None:
            nonlocal pending_size
            if self.on_progress is not None:
                pending.append(message)
                pending_size += len(message)
                if pending_size >= 4096 or time.monotonic() - last_flush >= 0.5:
                    flush()

        @contextmanager
        def logged_client(workspace: Path):
            with self.service._client(workspace=workspace) as client:
                try:
                    yield client
                finally:
                    runtime = getattr(
                        getattr(client, "_client", None), "_stderr_lines", None
                    )
                    if isinstance(runtime, deque):
                        lines = list(runtime.copy())
                        if lines:
                            log("\n[Codex runtime log] (last 400 lines)\n")
                            for line in lines:
                                log(redact_error(line) + "\n")

        error_context = ""
        try:
            prompt = transcription_prompt([page.page for page in request.pages])
            log(
                f"\n[Request] Model: {self.model}; pages: {', '.join(str(page.page) for page in request.pages)}\n\n[Prompt]\n{prompt}\n"
            )
            flush()
            with tempfile.TemporaryDirectory(prefix="songbook-codex-") as directory:
                items = [TextInput(text=prompt)]
                for page in request.pages:
                    path = Path(directory) / f"page-{page.page}.png"
                    path.write_bytes(page.png)
                    items.append(LocalImageInput(path=str(path)))
                with logged_client(Path(directory)) as client:
                    thread = client.thread_start(
                        model=self.model,
                        cwd=directory,
                        ephemeral=True,
                        approval_mode=ApprovalMode.deny_all,
                    )
                    if self.on_progress is None:
                        result = thread.run(items, output_schema=schema)
                    else:
                        turn = thread.turn(items, output_schema=schema)
                        log(f"\n[Turn] Started {turn.id}\n")
                        flush()
                        response_seen = False

                        def observed():
                            nonlocal response_seen, error_context
                            section = ""
                            seen = set()
                            for event in turn.stream():
                                if event.method in (
                                    "item/reasoning/summaryTextDelta",
                                    "item/agentMessage/delta",
                                ):
                                    label = (
                                        "Reasoning summary"
                                        if event.method
                                        == "item/reasoning/summaryTextDelta"
                                        else "Response"
                                    )
                                    if label == "Response":
                                        response_seen = True
                                    if section != label:
                                        log(f"\n[{label}]\n")
                                        section = label
                                    log(event.payload.delta)
                                elif event.method == "turn/completed":
                                    completed = event.payload.turn
                                    state = getattr(
                                        completed.status, "value", str(completed.status)
                                    )
                                    log(f"\n[Turn] {state}\n")
                                    if completed.error:
                                        log(
                                            f"[Turn error] {redact_error(completed.error.message or '')}\n"
                                        )
                                        detail = getattr(
                                            completed.error, "additional_details", None
                                        )
                                        if detail:
                                            log(
                                                f"[Error details] {redact_error(detail)}\n"
                                            )
                                        info = getattr(
                                            completed.error, "codex_error_info", None
                                        )
                                        if info is not None:
                                            value = (
                                                info.model_dump_json()
                                                if hasattr(info, "model_dump_json")
                                                else str(getattr(info, "value", info))
                                            )
                                            log(
                                                f"[Error category] {redact_error(value)}\n"
                                            )
                                            error_context = value
                                elif event.method in ("item/started", "item/completed"):
                                    item = getattr(event.payload, "item", None)
                                    item = getattr(item, "root", item)
                                    kind = getattr(item, "type", "unknown")
                                    kind = str(getattr(kind, "value", kind))
                                    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", kind):
                                        kind = "unknown"
                                    log(f"\n[Event] {event.method}: {kind}\n")
                                    section = ""
                                elif event.method not in seen:
                                    seen.add(event.method)
                                    log(f"\n[Event] {event.method}\n")
                                    section = ""
                                yield event

                        result = _collect_turn_result(observed(), turn_id=turn.id)
                        if not response_seen and result.final_response:
                            log(f"\n[Response]\n{result.final_response}\n")
            if result.status != TurnStatus.completed:
                raise RuntimeError("Codex turn did not complete")
            data = json.loads(result.final_response or "")
            if (
                isinstance(data, dict)
                and isinstance(data.get("source"), str)
                and not data["source"].strip()
            ):
                log(
                    "\n[Result] Codex returned an empty draft; see the response above for its explanation.\n"
                )
                raise ConversionFailure("codex_empty_draft")
            if (
                not isinstance(data.get("source"), str)
                or not data["source"].strip()
                or not isinstance(data.get("uncertainties"), list)
                or any(not isinstance(x, str) for x in data["uncertainties"])
            ):
                raise ValueError("Invalid draft")
            usage = (
                result.usage.model_dump(mode="json", by_alias=True)
                if result.usage
                else {}
            )
            if usage:
                log(f"\n[Usage] {json.dumps(usage)}\n")
            log("\n[Result] Structured response received; checking draft for review.\n")
            flush()
            return VisionDraft(
                data["source"], data["uncertainties"], self.model, usage, result.id
            )
        except ConversionFailure:
            flush()
            raise
        except Exception as error:  # noqa: BLE001 - SDK errors can contain private content
            log(f"\n[Error] {type(error).__name__}: {redact_error(str(error))}\n")
            flush()
            raise failure_for(error, context=error_context) from None
