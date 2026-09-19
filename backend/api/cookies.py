"""
Session cookies. Tokens live only in httpOnly cookies, so page scripts (and therefore any XSS) can never read them.
SameSite=Strict plus the required custom header (see app.py) covers cross-site request forgery.
"""
from __future__ import annotations

from fastapi import Request, Response

from backend.core.config import get_settings

ACCESS_COOKIE = "px_access"
REFRESH_COOKIE = "px_refresh"
_REFRESH_PATH = "/api/auth"
_REFRESH_MAX_AGE_S = 60 * 60 * 24 * 7


def set_session(response: Response, *, access_token: str, refresh_token: str | None, expires_in: int) -> None:
    secure = get_settings().is_production
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=max(expires_in, 60), httponly=True, secure=secure,
                        samesite="strict", path="/")
    if refresh_token:
        response.set_cookie(REFRESH_COOKIE, refresh_token, max_age=_REFRESH_MAX_AGE_S, httponly=True, secure=secure,
                            samesite="strict", path=_REFRESH_PATH)


def clear_session(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_PATH)


def access_token(request: Request) -> str | None:
    return request.cookies.get(ACCESS_COOKIE)


def refresh_token(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE)
