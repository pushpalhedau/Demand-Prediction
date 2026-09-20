"""
Sign-in for the admin console. Kept in its own router (and its own cookie namespace, see
backend/api/cookies.py) so an operator session can never be mistaken for a customer one.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.api import cookies
from backend.api.deps import CurrentOperator
from backend.core.errors import AuthError
from backend.services import identity

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.get("/me")
def me(operator: CurrentOperator):
    return {"email": operator.email}


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


def _issue(response: Response, session: identity.OperatorSession) -> dict:
    cookies.set_admin_session(response, access_token=session.access_token or "", refresh_token=session.refresh_token,
                              expires_in=session.expires_at - int(time.time()))
    return {"email": session.operator.email}


@router.post("/login")
def login(body: LoginBody, response: Response):
    return _issue(response, identity.sign_in_operator(body.email.strip(), body.password))


@router.post("/refresh")
def refresh(request: Request, response: Response):
    token = cookies.admin_refresh_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not signed in.")
    try:
        return _issue(response, identity.refresh_operator(token))
    except AuthError:
        cookies.clear_admin_session(response)
        raise


@router.post("/logout", status_code=204)
def logout(response: Response):
    cookies.clear_admin_session(response)
