from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.api import cookies
from backend.core.errors import AuthError
from backend.services import identity

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


def _issue(response: Response, session: identity.CustomerSession) -> dict:
    cookies.set_session(response, access_token=session.access_token or "", refresh_token=session.refresh_token,
                        expires_in=session.expires_at - int(time.time()))
    return {"email": session.identity.email, "organisation": session.tenant_name}


@router.post("/login")
def login(body: LoginBody, response: Response):
    return _issue(response, identity.sign_in_customer(body.email.strip(), body.password))


@router.post("/refresh")
def refresh(request: Request, response: Response):
    token = cookies.refresh_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in.")
    try:
        return _issue(response, identity.refresh_customer(token))
    except AuthError:
        cookies.clear_session(response)
        raise


@router.post("/logout", status_code=204)
def logout(response: Response):
    cookies.clear_session(response)
