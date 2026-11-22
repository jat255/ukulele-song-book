"""Local development application factory for Uvicorn reload."""

from dataclasses import replace

from .config import settings_from_environment
from .main import create_app


def create_dev_app():
    settings = settings_from_environment()
    if settings.loopback_http:
        settings = replace(
            settings,
            allowed_origins=(
                "http://127.0.0.1:8000",
                "http://localhost:8000",
                "http://127.0.0.1:5173",
                "http://localhost:5173",
            ),
        )
    return create_app(settings)
