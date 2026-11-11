"""Optional selected-PNG Anthropic Messages adapter."""

import base64
import json

import httpx

from .base import ProviderStatus, VisionDraft, VisionRequest


class AnthropicProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        client: httpx.Client | None = None,
        max_tokens: int = 4096,
        input_rate: float | None = None,
        output_rate: float | None = None,
    ):
        self._api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.client = client or httpx.Client(timeout=120)

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            bool(self._api_key and self.model),
            "anthropic",
            self.model,
            rate_basis={
                "input_usd_per_million": self.input_rate,
                "output_usd_per_million": self.output_rate,
            }
            if self.input_rate is not None and self.output_rate is not None
            else None,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float | None:
        if self.input_rate is None or self.output_rate is None:
            return None
        return (
            input_tokens * self.input_rate + output_tokens * self.output_rate
        ) / 1_000_000

    def convert(self, request: VisionRequest) -> VisionDraft:
        if not self.status().available or not 1 <= len(request.pages) <= 5:
            raise ValueError("Provider is unavailable or selection invalid")
        content = []
        for page in request.pages:
            content.append({"type": "text", "text": f"Selected page {page.page}"})
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(page.png).decode("ascii"),
                    },
                }
            )
        content.append(
            {
                "type": "text",
                "text": "Transcribe the selected pages to ChordPro. Do not invent missing content. Return JSON with source and uncertainties.",
            }
        )
        try:
            response = self.client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self._api_key, "anthropic-version": "2023-06-01"},
                json={
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "messages": [{"role": "user", "content": content}],
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("model") != self.model:
                raise ValueError("Provider response model differs from authorization")
            if data.get("stop_reason") != "end_turn":
                raise ValueError("Provider response incomplete")
            text = "".join(
                item.get("text", "")
                for item in data["content"]
                if item.get("type") == "text"
            )
            result = json.loads(text)
            if not isinstance(result, dict):
                raise TypeError("Invalid provider result")
            if not isinstance(result.get("source"), str) or not isinstance(
                result.get("uncertainties"), list
            ):
                raise TypeError("Invalid provider result")
            return VisionDraft(
                result["source"],
                result["uncertainties"],
                data["model"],
                data.get("usage", {}),
                data["id"],
                self.estimate_cost(
                    data.get("usage", {}).get("input_tokens", 0),
                    data.get("usage", {}).get("output_tokens", 0),
                )
                if "input_tokens" in data.get("usage", {})
                and "output_tokens" in data.get("usage", {})
                else None,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            raise ValueError("Vision conversion failed or was incomplete") from None
