"""Authenticated configuration; explicit tests never read collection content."""

import hashlib
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from PIL import Image, ImageDraw
from pydantic import BaseModel

from ..imports.failures import ConversionFailure, details
from ..imports.provider_settings import (
    ProviderEdit,
    load_settings,
    make_provider,
    public_settings,
    save_settings,
)
from ..imports.providers.base import SelectedPage, VisionRequest
from ..storage.arrangements import ConflictError
from .auth import require_csrf, require_session

router = APIRouter(prefix="/api/provider")
session = Depends(require_session)


@router.get("/settings")
def get_settings(request: Request, principal=session):
    try:
        return public_settings(load_settings(request.app.state.store))
    except (ValueError, OSError, KeyError, TypeError):
        raise HTTPException(
            503,
            detail="Provider settings are unreadable; restore the private configuration file.",
        ) from None


@router.put("/settings")
def put_settings(body: ProviderEdit, request: Request, principal=session):
    require_csrf(request, principal)
    try:
        return public_settings(save_settings(request.app.state.store, body))
    except ConflictError:
        raise HTTPException(
            409, detail="Settings changed elsewhere. Reopen the dialog before saving."
        ) from None
    except (ValueError, OSError, KeyError, TypeError):
        raise HTTPException(
            400,
            detail="Invalid settings. Use a valid HTTPS endpoint (or HTTP loopback), service type, name and model.",
        ) from None


class TestRequest(BaseModel):
    revision: str
    authorize_synthetic: bool = False


@router.post("/test")
def test_connection(body: TestRequest, request: Request, principal=session):
    require_csrf(request, principal)
    if not body.authorize_synthetic:
        raise HTTPException(
            400, detail="Explicit synthetic-image authorization required"
        )
    try:
        config = load_settings(request.app.state.store)
    except (ValueError, OSError, KeyError, TypeError):
        raise HTTPException(503, detail="Provider settings unavailable") from None
    if config["revision"] != body.revision:
        raise HTTPException(409, detail="Settings changed; save and test again")
    adapter = make_provider(request.app.state.store, config=config, allow_disabled=True)
    if adapter is None:
        raise HTTPException(
            400, detail="Configure a model and required credentials first"
        )
    image = Image.new("RGB", (400, 100), "white")
    ImageDraw.Draw(image).text((15, 30), "Synthetic test: [C] Hello", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    try:
        draft = adapter.convert(
            VisionRequest([SelectedPage(1, data, hashlib.sha256(data).hexdigest())])
        )
        if not draft.source.strip():
            raise ValueError("Empty draft")
    except ConversionFailure as error:
        feedback = details(error.code)
        raise HTTPException(
            502, detail=feedback["message"] + " " + feedback["hint"]
        ) from None
    except Exception:  # noqa: BLE001 -- provider errors must not disclose credentials or content
        raise HTTPException(
            502,
            detail="Vision test failed. Check endpoint, credentials, model image support and provider limits.",
        ) from None
    finally:
        getattr(adapter, "adapter", adapter).client.close()
    return {
        "ok": True,
        "message": "Synthetic image returned a structured draft. Real-song fidelity still requires review.",
    }
