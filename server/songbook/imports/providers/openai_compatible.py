"""Selected-image Chat Completions adapter; no SDK or provider-specific model list."""

import base64
import json

import httpx

from .base import ProviderStatus, VisionDraft


class CompatibleProvider:
    def __init__(self, base_url, api_key, model, *, client=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(
            timeout=120, follow_redirects=False, trust_env=False
        )

    def status(self):
        return ProviderStatus(True, "openai-compatible", self.model)

    def convert(self, request):
        if not 1 <= len(request.pages) <= 5:
            raise ValueError("Invalid page selection")
        content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/png;base64,"
                    + base64.b64encode(page.png).decode()
                },
            }
            for page in request.pages
        ]
        content.append(
            {
                "type": "text",
                "text": "Transcribe these selected pages in order to ChordPro. Do not invent missing content. Return only a JSON object with source (string) and uncertainties (array). Preserve chord positions, sections, and literal text tablature. Mark missing or uncertain material for review.",
            }
        )
        try:
            with self.client.stream(
                "POST",
                self.base_url + "/chat/completions",
                headers={"Authorization": "Bearer " + self.api_key}
                if self.api_key
                else {},
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "stream": False,
                    "messages": [{"role": "user", "content": content}],
                },
                follow_redirects=False,
            ) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise ValueError("Response too large")
            result = json.loads(data)
            choice = result["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ValueError("Incomplete response")
            raw = choice["message"]["content"]
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            draft = json.loads(raw)
            if not isinstance(draft["source"], str) or not isinstance(
                draft["uncertainties"], list
            ):
                raise TypeError("Invalid draft")
            if not isinstance(result["model"], str) or not isinstance(
                result["id"], str
            ):
                raise TypeError("Invalid response")
            return VisionDraft(
                draft["source"],
                draft["uncertainties"],
                result["model"],
                result.get("usage", {}),
                result["id"],
            )
        except (
            httpx.HTTPError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            AttributeError,
        ):
            raise ValueError("Vision conversion failed or was incomplete") from None
