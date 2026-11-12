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
