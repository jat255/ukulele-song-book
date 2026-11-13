import base64
import json

import httpx
import pytest

from server.songbook.imports.providers.base import SelectedPage, VisionRequest


def test_compatible_provider_sends_inline_images_and_validates_result():
    from server.songbook.imports.providers.openai_compatible import CompatibleProvider

    def respond(request):
        assert str(request.url) == "https://example.test/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "vision-model"
        assert request.headers["Authorization"] == "Bearer synthetic-key"
        assert (
            body["messages"][0]["content"][0]["image_url"]["url"]
            == "data:image/png;base64," + base64.b64encode(b"synthetic-image").decode()
        )
        return httpx.Response(
            200,
            json={
                "id": "test-request",
                "model": "vision-model-actual",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "source": "{title: Synthetic}\n[C]Hello",
                                    "uncertainties": ["alignment"],
                                }
                            )
                        },
                    }
                ],
                "usage": {"prompt_tokens": 1},
            },
        )

    adapter = CompatibleProvider(
        "https://example.test/v1",
        "synthetic-key",
        "vision-model",
        client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    draft = adapter.convert(
        VisionRequest([SelectedPage(1, b"synthetic-image", "hash")])
    )
    assert (
        draft.source.startswith("{title: Synthetic}")
        and draft.model == "vision-model-actual"
    )


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, text="synthetic-key private data"),
        httpx.Response(302, headers={"Location": "https://other.example"}),
        httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "length", "message": {"content": "{}"}}]
            },
        ),
        httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "not JSON"}}
                ]
            },
        ),
        httpx.Response(
            200,
            json={
                "id": "x",
                "model": "x",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"source":123,"uncertainties":[]}'},
                    }
                ],
            },
        ),
    ],
)
def test_bad_compatible_results_are_sanitized(response):
    from server.songbook.imports.providers.openai_compatible import CompatibleProvider

    adapter = CompatibleProvider(
        "https://example.test/v1",
        "synthetic-key",
        "vision-model",
        client=httpx.Client(transport=httpx.MockTransport(lambda request: response)),
    )
    with pytest.raises(ValueError, match="Vision conversion failed") as error:
        adapter.convert(VisionRequest([SelectedPage(1, b"synthetic-image", "hash")]))
    assert "synthetic-key" not in str(error.value)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "provider_auth"),
        (403, "provider_auth"),
        (429, "provider_rate_limit"),
        (404, "provider_model_or_endpoint"),
        (413, "provider_request_too_large"),
        (400, "provider_request_invalid"),
        (503, "provider_unavailable"),
    ],
)
def test_provider_failures_expose_only_safe_actionable_codes(status, code):
    from server.songbook.imports.providers.openai_compatible import CompatibleProvider

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status, text="private provider payload synthetic-key"
            )
        )
    )
    adapter = CompatibleProvider(
        "https://example.test/v1", "synthetic-key", "vision", client=client
    )
    with pytest.raises(ValueError) as caught:
        adapter.convert(VisionRequest([SelectedPage(1, b"image", "hash")]))
    assert getattr(caught.value, "code", None) == code
    assert "private provider payload" not in str(
        caught.value
    ) and "synthetic-key" not in str(caught.value)


def test_truncated_and_timeout_responses_have_distinct_feedback():
    from server.songbook.imports.providers.openai_compatible import CompatibleProvider

    def timeout(request):
        raise httpx.ReadTimeout("private request context", request=request)

    for transport, code in [
        (httpx.MockTransport(timeout), "provider_timeout"),
        (
            httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"choices": [{"finish_reason": "length"}]}
                )
            ),
            "provider_output_truncated",
        ),
    ]:
        adapter = CompatibleProvider(
            "https://example.test/v1",
            "synthetic-key",
            "vision",
            client=httpx.Client(transport=transport),
        )
        with pytest.raises(ValueError) as error:
            adapter.convert(VisionRequest([SelectedPage(1, b"image", "hash")]))
        assert error.value.code == code and "private request context" not in str(
            error.value
        )
