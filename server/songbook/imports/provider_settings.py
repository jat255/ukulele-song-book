"""Private operator configuration, deliberately excluded from library archives."""

import hashlib
import json
import os
import tempfile
import uuid
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..storage.arrangements import ConflictError
from .failures import ConversionFailure


class ProviderEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str = Field(max_length=100)
    name: str = Field(min_length=1, max_length=100)
    protocol: str = Field(max_length=30)
    base_url: str = Field(max_length=1000)
    model: str = Field(min_length=1, max_length=200)
    enabled: bool = False
    api_key: SecretStr | None = None


def validate_url(value):
    url = urlsplit(value)
    if (
        url.scheme not in ("http", "https")
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or (
            url.scheme == "http"
            and url.hostname not in ("localhost", "127.0.0.1", "::1")
        )
    ):
        raise ValueError(
            "Use HTTPS, or HTTP for a loopback endpoint, without URL credentials or query parameters."
        )
    if url.port is not None and not 1 <= url.port <= 65535:
        raise ValueError("Invalid endpoint port")
    return value.rstrip("/")


def load_settings(store):
    path = store.root / ".ai-provider.json"
    if path.is_symlink():
        raise ValueError("Invalid provider configuration file")
    if path.exists():
        if path.stat().st_size > 16384:
            raise ValueError("Invalid provider configuration")
        config = json.loads(path.read_text())
        ProviderEdit.model_validate(config)
        validate_url(config["base_url"])
        if config["protocol"] not in ("anthropic", "openai-compatible"):
            raise ValueError("Invalid provider type")
        return config
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    model = os.environ.get("SONGBOOK_ANTHROPIC_MODEL", "")
    enabled = os.environ.get("SONGBOOK_ALLOW_EXTERNAL_AI") == "true"
    revision = hashlib.sha256(json.dumps([key, model, enabled]).encode()).hexdigest()
    return {
        "revision": revision,
        "name": "Anthropic",
        "protocol": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "model": model,
        "enabled": enabled,
        "api_key": key,
        "legacy": True,
    }


def public_settings(config):
    return {
        **{
            key: config[key]
            for key in ("revision", "name", "protocol", "base_url", "model", "enabled")
        },
        "has_api_key": bool(config.get("api_key")),
    }


def save_settings(store, edit):
    if edit.protocol not in ("anthropic", "openai-compatible"):
        raise ValueError("Unsupported service type")
    url = validate_url(edit.base_url)
    if edit.protocol == "anthropic" and url != "https://api.anthropic.com/v1":
        raise ValueError(
            "Anthropic uses https://api.anthropic.com/v1; choose OpenAI-compatible for custom endpoints."
        )
    with store._lock():
        current = load_settings(store)
        if edit.revision != current["revision"]:
            raise ConflictError("Provider configuration changed")
        same_endpoint = (
            current["protocol"] == edit.protocol and current["base_url"] == url
        )
        key = (
            edit.api_key.get_secret_value()
            if edit.api_key is not None
            else current.get("api_key", "")
            if same_endpoint
            else ""
        )
        if (
            len(key) > 4096
            or not key.isascii()
            or any(ord(char) < 32 or ord(char) == 127 for char in key)
        ):
            raise ValueError("Invalid API key")
        config = {
            "revision": str(uuid.uuid4()),
            "name": edit.name.strip(),
            "protocol": edit.protocol,
            "base_url": url,
            "model": edit.model.strip(),
            "enabled": edit.enabled,
            "api_key": key,
        }
        if not config["name"] or not config["model"]:
            raise ValueError("Service name and model are required")
        fd, name = tempfile.mkstemp(prefix=".ai-provider-", dir=store.root)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(config, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, store.root / ".ai-provider.json")
            directory = os.open(store.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return config


class BoundProvider:
    """Revision identity prevents a changed destination from consuming old consent."""

    def __init__(self, adapter, config, store):
        self.adapter = adapter
        self.config = config
        self.store = store

    def status(self):
        from dataclasses import replace

        status = self.adapter.status()
        return replace(
            status,
            available=status.available
            and load_settings(self.store)["revision"] == self.config["revision"],
            provider=self.config["protocol"]
            if self.config.get("legacy")
            else self.config["protocol"] + ":" + self.config["revision"],
        )

    def convert(self, request):
        if not self.status().available:
            raise ConversionFailure("provider_changed")
        return self.adapter.convert(request)


def make_provider(store, *, client=None, config=None, allow_disabled=False):
    config = config or load_settings(store)
    if not config["enabled"] and not allow_disabled:
        return None
    if not config["model"]:
        return None
    validate_url(config["base_url"])
    if config["protocol"] == "anthropic":
        from .providers.anthropic import AnthropicProvider

        if not config.get("api_key"):
            return None
        adapter = AnthropicProvider(config["api_key"], config["model"], client=client)
    else:
        from .providers.openai_compatible import CompatibleProvider

        adapter = CompatibleProvider(
            config["base_url"],
            config.get("api_key", ""),
            config["model"],
            client=client,
        )
    return BoundProvider(adapter, config, store)


def provider_status(store):
    config = load_settings(store)
    configured = bool(
        config["model"]
        and (config.get("api_key") or config["protocol"] == "openai-compatible")
    )
    identity = (
        config["protocol"]
        if config.get("legacy")
        else config["protocol"] + ":" + config["revision"]
    )
    return {
        "provider": identity,
        "name": config["name"],
        "model": config["model"] or None,
        "configured": configured,
        "available": bool(config["enabled"] and configured),
        "cost_estimate": None,
        "revision": config["revision"],
    }
