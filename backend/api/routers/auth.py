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
    """
    The one sign-in form for customers and operators. The account decides which session it gets (see
    identity.sign_in), and the browser is never left holding both kinds: signing in as one clears the other's cookies.
    """
    signed_in = identity.sign_in(body.email.strip(), body.password)
    if signed_in.operator is not None:
        session = signed_in.operator
        cookies.clear_session(response)
        cookies.set_admin_session(response, access_token=session.access_token or "", refresh_token=session.refresh_token,
                                  expires_in=session.expires_at - int(time.time()))
        return {"kind": "operator", "email": session.operator.email, "organisation": None}
    cookies.clear_admin_session(response)
    return {"kind": "customer", **_issue(response, signed_in.customer)}


@router.post("/login/customer")
def login_customer(body: LoginBody, response: Response):
    """Customer-only sign-in (refuses operator accounts). Kept for clients that must never receive an operator session."""
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
