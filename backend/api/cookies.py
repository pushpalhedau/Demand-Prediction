"""
Session cookies. Tokens live only in httpOnly cookies, so page scripts (and therefore any XSS) can never read them.
SameSite=Strict plus the required custom header (see app.py) covers cross-site request forgery.

Customer and operator sessions use different cookie names on purpose: they are different kinds of login (see
backend/services/identity.py), and a browser that somehow has both apps open must never confuse the two.
"""
from __future__ import annotations

from fastapi import Request, Response

from backend.core.config import get_settings

ACCESS_COOKIE = "px_access"
REFRESH_COOKIE = "px_refresh"
_REFRESH_PATH = "/api/auth"

ADMIN_ACCESS_COOKIE = "px_admin_access"
ADMIN_REFRESH_COOKIE = "px_admin_refresh"
_ADMIN_REFRESH_PATH = "/api/admin/auth"

_REFRESH_MAX_AGE_S = 60 * 60 * 24 * 7


def _set(response: Response, *, access_name: str, refresh_name: str, refresh_path: str, access_token: str,
         refresh_token: str | None, expires_in: int) -> None:
    secure = get_settings().is_production
    response.set_cookie(access_name, access_token, max_age=max(expires_in, 60), httponly=True, secure=secure,
                        samesite="strict", path="/")
    if refresh_token:
        response.set_cookie(refresh_name, refresh_token, max_age=_REFRESH_MAX_AGE_S, httponly=True, secure=secure,
                            samesite="strict", path=refresh_path)


def set_session(response: Response, *, access_token: str, refresh_token: str | None, expires_in: int) -> None:
    _set(response, access_name=ACCESS_COOKIE, refresh_name=REFRESH_COOKIE, refresh_path=_REFRESH_PATH,
        access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


def clear_session(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_PATH)


def access_token(request: Request) -> str | None:
    return request.cookies.get(ACCESS_COOKIE)


def refresh_token(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE)


def set_admin_session(response: Response, *, access_token: str, refresh_token: str | None, expires_in: int) -> None:
    _set(response, access_name=ADMIN_ACCESS_COOKIE, refresh_name=ADMIN_REFRESH_COOKIE, refresh_path=_ADMIN_REFRESH_PATH,
        access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


def clear_admin_session(response: Response) -> None:
    response.delete_cookie(ADMIN_ACCESS_COOKIE, path="/")
    response.delete_cookie(ADMIN_REFRESH_COOKIE, path=_ADMIN_REFRESH_PATH)


def admin_access_token(request: Request) -> str | None:
    return request.cookies.get(ADMIN_ACCESS_COOKIE)


def admin_refresh_token(request: Request) -> str | None:
    return request.cookies.get(ADMIN_REFRESH_COOKIE)
