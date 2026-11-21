"""Private Codex SDK account discovery for the songbook operator."""

import json
import os
import threading
from pathlib import Path
from urllib.parse import urlparse

from openai_codex import Codex, CodexConfig
from openai_codex.generated.v2_all import (
    GetAccountRateLimitsResponse,
    ModelListResponse,
)


def codex_home_for(library_root: Path) -> Path:
    return Path(
        os.environ.get(
            "SONGBOOK_CODEX_HOME",
            str(library_root.parent / (library_root.name + "-codex")),
        )
    )


class CodexService:
    def __init__(self, codex_home: Path):
        self.codex_home = codex_home
        self._login_lock = threading.Lock()
        self._login = None
        self._login_state = "idle"

    def _client(self, *, workspace: Path | None = None):
        if self.codex_home.is_symlink():
            raise ValueError("Codex home must not be a symlink")
        self.codex_home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.codex_home.chmod(0o700)
        overrides = ['model_provider="openai"', 'cli_auth_credentials_store="file"']
        if workspace is not None:
            overrides.extend(
                [
                    'default_permissions="songbook_transcription"',
                    'permissions.songbook_transcription.filesystem={":minimal"="read",'
                    + json.dumps(str(workspace.resolve()))
                    + '="read"}',
                    "permissions.songbook_transcription.network.enabled=false",
                    "features.shell_tool=false",
                    "features.unified_exec=false",
                    "features.view_image=false",
                    "features.image_generation=false",
                    "features.skill_search=false",
                    "features.skip_host_skill_discovery=true",
                    "agents.enabled=false",
                    "mcp_servers={}",
                    'web_search="disabled"',
                ]
            )
        return Codex(
            CodexConfig(
                cwd=str(workspace or self.codex_home),
                env={
                    "CODEX_HOME": str(self.codex_home),
                    "OPENAI_API_KEY": "",
                    "CODEX_API_KEY": "",
                },
                config_overrides=tuple(overrides),
            )
        )

    def status(self) -> dict:
        with self._client() as client:
            wrapped = client.account().account
            account = wrapped.root if wrapped else None
            if not account or account.type != "chatgpt":
                return {"connected": False, "email": None, "plan": None, "models": []}
            page = client.models()
            catalog = list(page.data)
            seen = set()
            cursor = getattr(page, "next_cursor", None)
            while cursor:
                if cursor in seen or len(seen) >= 100:
                    raise ValueError("Invalid Codex model catalog pagination")
                seen.add(cursor)
                page = client._client.request(
                    "model/list",
                    {"includeHidden": False, "cursor": cursor},
                    response_model=ModelListResponse,
                )
                catalog.extend(page.data)
                cursor = page.next_cursor
            models = [
                {
                    "id": item.model,
                    "name": item.display_name,
                    "default": item.is_default,
                }
                for item in catalog
                if not item.hidden
                and (
                    item.input_modalities is None
                    or any(
                        getattr(modality, "value", modality) == "image"
                        for modality in item.input_modalities
                    )
                )
            ]
            return {
                "connected": True,
                "email": account.email,
                "plan": account.plan_type,
                "models": models,
            }

    def start_login(self) -> dict:
        with self._login_lock:
            if self._login is not None:
                raise ValueError("A Codex sign-in is already in progress")
            client = self._client()
            try:
                handle = client.login_chatgpt_device_code()
                url = urlparse(handle.verification_url)
                if url.scheme != "https" or url.netloc != "auth.openai.com":
                    raise ValueError("Invalid Codex verification address")
                self._login = handle
                self._login_state = "pending"
            except Exception:
                client.close()
                raise

            def wait_for_login():
                state = "failed"
                try:
                    state = "complete" if handle.wait().success else "failed"
                except Exception:  # noqa: BLE001 - do not log SDK auth payloads
                    state = "failed"
                finally:
                    client.close()
                    with self._login_lock:
                        self._login = None
                        self._login_state = state

            threading.Thread(target=wait_for_login, daemon=True).start()
            return {
                "verification_url": handle.verification_url,
                "user_code": handle.user_code,
            }

    def login_status(self) -> dict:
        with self._login_lock:
            result = {"state": self._login_state}
            if self._login is not None:
                result.update(
                    {
                        "verification_url": self._login.verification_url,
                        "user_code": self._login.user_code,
                    }
                )
            return result

    def cancel_login(self) -> None:
        with self._login_lock:
            handle = self._login
        if handle is None:
            raise ValueError("No Codex sign-in is in progress")
        handle.cancel()

    def usage(self) -> dict:
        with self._client() as client:
            result = client._client.request(
                "account/rateLimits/read",
                {},
                response_model=GetAccountRateLimitsResponse,
            )

            def window(value):
                return (
                    None
                    if value is None
                    else {
                        "used_percent": value.used_percent,
                        "window_minutes": value.window_duration_mins,
                        "resets_at": value.resets_at,
                    }
                )

            return {
                "primary": window(result.rate_limits.primary),
                "secondary": window(result.rate_limits.secondary),
            }

    def logout(self) -> None:
        with self._login_lock:
            if self._login is not None:
                raise ValueError("Wait for the active sign-in to finish")
            with self._client() as client:
                client.logout()
