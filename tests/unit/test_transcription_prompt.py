"""The request contract must teach inline anchoring to both image adapters."""

import json

import httpx
import pytest

from server.songbook.imports.providers.base import SelectedPage, VisionRequest


@pytest.mark.parametrize("kind", ["anthropic", "compatible"])
def test_both_providers_send_character_anchor_examples_and_page_order(kind):
    captured = []

    def reply(request):
        captured.append(json.loads(request.content))
        draft = json.dumps(
            {"source": "{title: Synthetic}\nsi[Am]lver", "uncertainties": []}
        )
        if kind == "anthropic":
            return httpx.Response(
                200,
                json={
                    "id": "synthetic",
                    "model": "synthetic-model",
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": draft}],
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "synthetic",
                "model": "synthetic-model",
                "choices": [{"finish_reason": "stop", "message": {"content": draft}}],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(reply))
    if kind == "anthropic":
        from server.songbook.imports.providers.anthropic import AnthropicProvider

        adapter = AnthropicProvider("synthetic-key", "synthetic-model", client=client)
    else:
        from server.songbook.imports.providers.openai_compatible import (
            CompatibleProvider,
        )

        adapter = CompatibleProvider(
            "https://example.test/v1", "synthetic-key", "synthetic-model", client=client
        )
    adapter.convert(
        VisionRequest(
            [SelectedPage(2, b"synthetic", "x"), SelectedPage(5, b"synthetic", "y")]
        )
    )
    prompt = "\n".join(
        item["text"]
        for item in captured[0]["messages"][0]["content"]
        if item["type"] == "text"
    )
    assert "si[Am]lver" in prompt
    assert "[C]Blue  [G]sky" in prompt
    assert "2, 5" in prompt
    assert "removing" in prompt and "unchanged" in prompt
    assert "chord-only" in prompt and "uncertainties" in prompt
