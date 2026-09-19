import os
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

_TIMEOUT = 10


class AuthError(Exception):
    """Raised with a message that is safe to show to the end user."""


@dataclass(frozen=True)
class Identity:
    user_id: str
    email: str
    tenant_id: uuid.UUID
    role: str


def _url() -> str:
    """
    Base URL of the auth API. AUTH_BASE_URL points at a self-hosted GoTrue (free, e.g. http://localhost:9999);
    otherwise it is a hosted Supabase project, whose gateway serves the same API under /auth/v1.
    """
    base = os.getenv("AUTH_BASE_URL", "").rstrip("/")
    if base:
        return base
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise AuthError("Authentication is not configured (set AUTH_BASE_URL or SUPABASE_URL).")
    return f"{url}/auth/v1"


def is_configured() -> bool:
    return bool(os.getenv("AUTH_BASE_URL") or (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY")))


def _anon_headers() -> dict:
    return {"apikey": os.getenv("SUPABASE_ANON_KEY", ""), "Content-Type": "application/json"}


def _service_key() -> str:
    """Admin credential: the hosted service-role key, or (self-hosted) a short-lived token signed with the JWT secret."""
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if key:
        return key
    secret = os.getenv("SUPABASE_JWT_SECRET")
    if secret:
        now = int(time.time())
        return jwt.encode({"role": "service_role", "aud": "authenticated", "iat": now, "exp": now + 300},
                          secret, algorithm="HS256")
    raise AuthError("No admin credential: set SUPABASE_SERVICE_ROLE_KEY or SUPABASE_JWT_SECRET.")


def sign_in(email: str, password: str) -> dict:
    r = requests.post(f"{_url()}/token", params={"grant_type": "password"},
                      headers=_anon_headers(), json={"email": email, "password": password}, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise AuthError("Invalid email or password.")
    return r.json()


def refresh(refresh_token: str) -> dict:
    r = requests.post(f"{_url()}/token", params={"grant_type": "refresh_token"},
                      headers=_anon_headers(), json={"refresh_token": refresh_token}, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise AuthError("Your session has expired. Please sign in again.")
    return r.json()


@lru_cache(maxsize=1)
def _jwks_client() -> "jwt.PyJWKClient":
    return jwt.PyJWKClient(f"{_url()}/.well-known/jwks.json", cache_keys=True)


def verify_access_token(token: str) -> dict:
    """Validate signature, expiry and audience. HS256 shared secret (legacy projects) or JWKS (asymmetric keys)."""
    try:
        secret = os.getenv("SUPABASE_JWT_SECRET")
        if secret:
            return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
        key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["RS256", "ES256"], audience="authenticated")
    except jwt.ExpiredSignatureError:
        raise AuthError("Your session has expired. Please sign in again.")
    except jwt.PyJWTError:
        raise AuthError("Invalid session.")


def identity_from_claims(claims: dict) -> Identity:
    # app_metadata is writable only with the service-role key, never by the user
    # (unlike user_metadata), so the tenant claim can be trusted.
    meta = claims.get("app_metadata") or {}
    raw_tenant = meta.get("tenant_id")
    if not raw_tenant:
        raise AuthError("This account is not linked to an organisation. Contact support.")
    try:
        tenant_id = uuid.UUID(str(raw_tenant))
    except ValueError:
        raise AuthError("This account is not linked to a valid organisation. Contact support.")
    return Identity(user_id=claims["sub"], email=claims.get("email", ""), tenant_id=tenant_id,
                    role=meta.get("role", "tenant_user"))


@dataclass(frozen=True)
class Operator:
    """A platform operator (runs the admin console). Has no customer tenant."""
    user_id: str
    email: str


def operator_from_claims(claims: dict) -> Operator:
    """Only an account whose (service-key-only) app_metadata says platform_admin may use the console."""
    meta = claims.get("app_metadata") or {}
    if meta.get("role") != "platform_admin" or meta.get("tenant_id"):
        raise AuthError("This account cannot use the admin console.")
    return Operator(user_id=claims["sub"], email=claims.get("email", ""))


def _admin_headers() -> dict:
    key = _service_key()
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def admin_create_user(email: str, password: str, tenant_id=None, role: str = "tenant_admin") -> str:
    """
    Create a confirmed user. A customer user is pinned to a tenant; an operator (role platform_admin)
    has no tenant. Needs the service credential; server-side only.
    """
    meta = {"role": role}
    if tenant_id is not None:
        meta["tenant_id"] = str(tenant_id)
    r = requests.post(f"{_url()}/admin/users", headers=_admin_headers(),
                      json={"email": email, "password": password, "email_confirm": True, "app_metadata": meta},
                      timeout=_TIMEOUT)
    if r.status_code not in (200, 201):
        raise AuthError(f"Could not create user: {r.text}")
    return r.json()["id"]


def admin_list_users() -> list:
    """All users (paged internally). Filter by app_metadata.tenant_id client-side."""
    out, page = [], 1
    while True:
        r = requests.get(f"{_url()}/admin/users", headers=_admin_headers(),
                         params={"page": page, "per_page": 200}, timeout=_TIMEOUT)
        if r.status_code != 200:
            raise AuthError(f"Could not list users: {r.text}")
        users = r.json().get("users", [])
        out += users
        if len(users) < 200:
            return out
        page += 1


def admin_set_password(user_id: str, password: str) -> None:
    r = requests.put(f"{_url()}/admin/users/{user_id}", headers=_admin_headers(),
                     json={"password": password}, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise AuthError(f"Could not change password: {r.text}")


def admin_delete_user(user_id: str) -> None:
    r = requests.delete(f"{_url()}/admin/users/{user_id}", headers=_admin_headers(), timeout=_TIMEOUT)
    if r.status_code not in (200, 204):
        raise AuthError(f"Could not delete user: {r.text}")


def users_of_tenant(tenant_id) -> list:
    return [u for u in admin_list_users()
            if str((u.get("app_metadata") or {}).get("tenant_id")) == str(tenant_id)]
