"""Authenticated Codex connection and model discovery endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request

from .auth import Principal, require_csrf, require_session

router = APIRouter(prefix="/api/codex")
principal_dependency = Depends(require_session)


@router.get("/status")
def status(request: Request, principal: Principal = principal_dependency):
    try:
        return request.app.state.codex.status()
    except Exception as error:
        raise HTTPException(503, detail="Codex status is unavailable") from error


@router.post("/login")
def login(request: Request, principal: Principal = principal_dependency):
    require_csrf(request, principal)
    try:
        return request.app.state.codex.start_login()
    except ValueError as error:
        raise HTTPException(409, detail=str(error)) from None
    except Exception as error:
        raise HTTPException(503, detail="Could not start Codex sign-in") from error


@router.get("/usage")
def usage(request: Request, principal: Principal = principal_dependency):
    try:
        return request.app.state.codex.usage()
    except Exception as error:
        raise HTTPException(503, detail="Codex usage is unavailable") from error


@router.get("/login-status")
def login_status(request: Request, principal: Principal = principal_dependency):
    return request.app.state.codex.login_status()


@router.post("/cancel-login")
def cancel_login(request: Request, principal: Principal = principal_dependency):
    require_csrf(request, principal)
    try:
        request.app.state.codex.cancel_login()
        return {"ok": True}
    except ValueError as error:
        raise HTTPException(409, detail=str(error)) from None
    except Exception as error:
        raise HTTPException(503, detail="Could not cancel Codex sign-in") from error


@router.post("/logout")
def logout(request: Request, principal: Principal = principal_dependency):
    require_csrf(request, principal)
    try:
        request.app.state.codex.logout()
        return {"ok": True}
    except ValueError as error:
        raise HTTPException(409, detail=str(error)) from None
    except Exception as error:
        raise HTTPException(503, detail="Could not sign out of Codex") from error
