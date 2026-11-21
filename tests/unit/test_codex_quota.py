import time

import pytest

from server.songbook.imports.codex_provider import CodexVisionProvider
from server.songbook.imports.providers.base import VisionDraft, VisionRequest


RESET = int(time.time()) + 3600


def snapshot(primary, secondary=10, *, reset=RESET):
    return {
        "primary": {"used_percent": primary, "window_minutes": 300, "resets_at": reset},
        "secondary": {
            "used_percent": secondary,
            "window_minutes": 10080,
            "resets_at": reset + 1000,
        },
    }


class Service:
    def __init__(self, values):
        self.values = iter(values)

    def usage(self):
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value


def test_quota_comparison_is_persisted_and_does_not_replace_token_usage(monkeypatch):
    provider = CodexVisionProvider(Service([snapshot(20, 4), snapshot(23, 5)]), "model")
    monkeypatch.setattr(
        provider,
        "_convert",
        lambda request: VisionDraft("song", [], "model", {"tokens": 10}, "id"),
        raising=False,
    )
    draft = provider.convert(VisionRequest([]))
    assert draft.usage == {"tokens": 10}
    assert draft.quota_usage["primary"]["delta_percent"] == 3
    assert draft.quota_usage["secondary"]["delta_percent"] == 1


def test_quota_reset_or_missing_snapshot_is_unavailable_without_failing_conversion(
    monkeypatch,
):
    provider = CodexVisionProvider(
        Service([snapshot(98), snapshot(2, reset=int(time.time()) + 7200)]), "model"
    )
    monkeypatch.setattr(
        provider,
        "_convert",
        lambda request: VisionDraft("song", [], "model", {}, "id"),
        raising=False,
    )
    quota = provider.convert(VisionRequest([])).quota_usage
    assert quota["primary"]["delta_percent"] is None
    provider.service = Service([RuntimeError("offline"), snapshot(3)])
    assert (
        provider.convert(VisionRequest([])).quota_usage["primary"]["delta_percent"]
        is None
    )


def test_failed_conversion_still_logs_quota_comparison(monkeypatch):
    output = []
    provider = CodexVisionProvider(
        Service([snapshot(20), snapshot(21)]), "model", on_progress=output.append
    )

    def fail(request):
        raise ValueError("conversion failed")

    monkeypatch.setattr(provider, "_convert", fail, raising=False)
    with pytest.raises(ValueError, match="conversion failed"):
        provider.convert(VisionRequest([]))
    assert "1 percentage point" in "".join(output)
