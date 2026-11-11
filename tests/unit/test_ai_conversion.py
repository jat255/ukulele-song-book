import hashlib
import json

import httpx
import pytest

from server.songbook.imports.ai import (
    AIConversionService,
    ConversionAuthorization,
    PageSelection,
)
from server.songbook.imports.providers.anthropic import AnthropicProvider
from server.songbook.imports.providers.base import SelectedPage, VisionRequest


def page(number, content):
    from io import BytesIO

    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (1, 1), (len(content) % 256, 0, 0)).save(output, format="PNG")
    png = output.getvalue() + (content if len(content) > 1_000_000 else b"")
    return SelectedPage(number, png, hashlib.sha256(png).hexdigest())


def test_disabled_without_configuration(tmp_path):
    service = AIConversionService(None, tmp_path / "requests.sqlite")
    assert not service.provider_status().available
    with pytest.raises(ValueError):
        service.convert(
            PageSelection("source", [page(1, b"png")]),
            ConversionAuthorization("source", (), "", "", False),
        )


def test_only_explicit_selected_pages_sent():
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "model": "test-model",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"source": "[C]Hi", "uncertainties": []}),
                    }
                ],
            },
        )

    provider = AnthropicProvider(
        "secret",
        "test-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = provider.convert(VisionRequest([page(2, b"first"), page(4, b"second")]))
    images = [x for x in captured[0]["messages"][0]["content"] if x["type"] == "image"]
    assert len(images) == 2
    assert result.source == "[C]Hi"
    assert "secret" not in json.dumps(captured)


def test_provider_failure_and_truncation_remain_drafts():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "model": "m",
                "stop_reason": "max_tokens",
                "usage": {},
                "content": [{"type": "text", "text": "truncated"}],
            },
        )

    provider = AnthropicProvider(
        "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ValueError):
        provider.convert(VisionRequest([page(1, b"x")]))


def test_no_silent_paid_retry_and_authorization_binding(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout")

    provider = AnthropicProvider(
        "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    service = AIConversionService(provider, tmp_path / "requests.sqlite")
    selected = PageSelection("source", [page(1, b"x")], source_hash="abc")
    auth = ConversionAuthorization(
        "source",
        (selected.pages[0].sha256,),
        "anthropic",
        "m",
        True,
        page_numbers=(1,),
        source_hash="abc",
    )
    with pytest.raises(ValueError):
        service.convert(selected, auth)
    with pytest.raises(ValueError):
        service.convert(selected, auth)
    assert len(calls) == 1


def test_cost_unknown_without_rates():
    provider = AnthropicProvider("secret", "m")
    assert provider.status().estimated_cost is None
    assert "secret" not in repr(provider.status())


def test_draft_is_parsed_and_remains_review_only(tmp_path):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "model": "m",
                "stop_reason": "end_turn",
                "usage": {},
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"source": "[C]Hello", "uncertainties": ["uncertain"]}
                        ),
                    }
                ],
            },
        )

    provider = AnthropicProvider(
        "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    service = AIConversionService(provider, tmp_path / "requests.sqlite")
    selected = PageSelection("source", [page(1, b"x")], source_hash="abc")
    result = service.convert(
        selected,
        ConversionAuthorization(
            "source",
            (selected.pages[0].sha256,),
            "anthropic",
            "m",
            True,
            page_numbers=(1,),
            source_hash="abc",
        ),
    )
    assert result.needs_visual_review
    assert result.source == "[C]Hello"
    assert result.source_refs[0]["page"] == 1


def test_explicit_new_authorization_allows_manual_retry(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout")

    service = AIConversionService(
        AnthropicProvider(
            "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
        ),
        tmp_path / "requests.sqlite",
    )
    selection = PageSelection("source", [page(1, b"x")], source_hash="abc")
    for nonce in ("first", "second"):
        with pytest.raises(ValueError):
            service.convert(
                selection,
                ConversionAuthorization(
                    "source",
                    (selection.pages[0].sha256,),
                    "anthropic",
                    "m",
                    True,
                    nonce,
                    page_numbers=(1,),
                    source_hash="abc",
                ),
            )
    assert len(calls) == 2


def test_errors_do_not_expose_secrets_or_provider_response():
    def handler(request):
        return httpx.Response(429, text="private lyrics and secret")

    provider = AnthropicProvider(
        "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ValueError) as error:
        provider.convert(VisionRequest([page(1, b"x")]))
    assert "secret" not in str(error.value)
    assert "private lyrics" not in str(error.value)


def test_authorization_cannot_be_reused_for_a_different_page_number(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    service = AIConversionService(
        AnthropicProvider(
            "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
        ),
        tmp_path / "requests.sqlite",
    )
    selected = PageSelection("source", [page(2, b"x")], source_hash="abc")
    auth = ConversionAuthorization(
        "source",
        (selected.pages[0].sha256,),
        "anthropic",
        "m",
        True,
        page_numbers=(1,),
        source_hash="abc",
    )
    with pytest.raises(ValueError):
        service.convert(selected, auth)
    assert not calls


def test_configured_rates_allow_estimate_and_actual_cost():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "model": "m",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1000, "output_tokens": 500},
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"source": "[C]Hi", "uncertainties": []}),
                    }
                ],
            },
        )

    provider = AnthropicProvider(
        "secret",
        "m",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        input_rate=2.0,
        output_rate=4.0,
    )
    assert provider.estimate_cost(1000, 500) == pytest.approx(0.004)
    assert provider.convert(
        VisionRequest([page(1, b"x")])
    ).actual_cost == pytest.approx(0.004)


def test_usage_and_request_identity_are_retained(tmp_path):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "request-1",
                "model": "m",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"source": "Hi", "uncertainties": []}),
                    }
                ],
            },
        )

    service = AIConversionService(
        AnthropicProvider(
            "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
        ),
        tmp_path / "requests.sqlite",
    )
    selected = PageSelection("source", [page(1, b"x")], source_hash="abc")
    draft = service.convert(
        selected,
        ConversionAuthorization(
            "source",
            (selected.pages[0].sha256,),
            "anthropic",
            "m",
            True,
            page_numbers=(1,),
            source_hash="abc",
        ),
    )
    assert draft.provider_metadata["request_id"] == "request-1"
    assert draft.provider_metadata["usage"]["input_tokens"] == 10


def test_large_page_is_rejected_before_network(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    service = AIConversionService(
        AnthropicProvider(
            "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
        ),
        tmp_path / "requests.sqlite",
    )
    selected = PageSelection(
        "source", [page(1, b"x" * (12_000_001))], source_hash="abc"
    )
    auth = ConversionAuthorization(
        "source",
        (selected.pages[0].sha256,),
        "anthropic",
        "m",
        True,
        page_numbers=(1,),
        source_hash="abc",
    )
    with pytest.raises(ValueError):
        service.convert(selected, auth)
    assert not calls


def test_non_png_is_rejected_before_network(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    service = AIConversionService(
        AnthropicProvider(
            "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
        ),
        tmp_path / "requests.sqlite",
    )
    selected = PageSelection(
        "source",
        [SelectedPage(1, b"not a png", hashlib.sha256(b"not a png").hexdigest())],
        source_hash="abc",
    )
    auth = ConversionAuthorization(
        "source",
        (selected.pages[0].sha256,),
        "anthropic",
        "m",
        True,
        page_numbers=(1,),
        source_hash="abc",
    )
    with pytest.raises(ValueError):
        service.convert(selected, auth)
    assert not calls


def test_png_header_alone_is_not_accepted(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    service = AIConversionService(
        AnthropicProvider(
            "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
        ),
        tmp_path / "requests.sqlite",
    )
    data = b"\x89PNG\r\n\x1a\ninvalid"
    selected = PageSelection(
        "source",
        [SelectedPage(1, data, hashlib.sha256(data).hexdigest())],
        source_hash="abc",
    )
    auth = ConversionAuthorization(
        "source",
        (selected.pages[0].sha256,),
        "anthropic",
        "m",
        True,
        page_numbers=(1,),
        source_hash="abc",
    )
    with pytest.raises(ValueError):
        service.convert(selected, auth)
    assert not calls


def test_unexpected_response_model_is_rejected():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "model": "unexpected",
                "stop_reason": "end_turn",
                "usage": {},
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"source": "Hi", "uncertainties": []}),
                    }
                ],
            },
        )

    provider = AnthropicProvider(
        "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ValueError):
        provider.convert(VisionRequest([page(1, b"x")]))


def test_status_discloses_configured_rate_basis():
    status = AnthropicProvider("secret", "m", input_rate=2.0, output_rate=4.0).status()
    assert status.rate_basis == {
        "input_usd_per_million": 2.0,
        "output_usd_per_million": 4.0,
    }
    assert status.estimated_cost is None


def test_authorization_rejects_different_source_hash(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    service = AIConversionService(
        AnthropicProvider(
            "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
        ),
        tmp_path / "requests.sqlite",
    )
    selected = PageSelection("source", [page(1, b"x")], source_hash="hash-a")
    auth = ConversionAuthorization(
        "source",
        (selected.pages[0].sha256,),
        "anthropic",
        "m",
        True,
        page_numbers=(1,),
        source_hash="hash-b",
    )
    with pytest.raises(ValueError):
        service.convert(selected, auth)
    assert not calls


def test_non_object_provider_json_is_rejected():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "model": "m",
                "stop_reason": "end_turn",
                "usage": {},
                "content": [{"type": "text", "text": "[]"}],
            },
        )

    provider = AnthropicProvider(
        "secret", "m", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ValueError):
        provider.convert(VisionRequest([page(1, b"x")]))
