"""
The shared sign-in form: one password check, and the account's own trusted claims decide whether the person is a
customer or an operator. No database or auth server needed: the auth client and tenant lookup are replaced.
"""
import time
import types
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.api import cookies
from backend.auth import client as auth_client
from backend.core.errors import AuthError
from backend.core.security import LoginThrottle
from backend.services import identity

SECRET = "test-secret-at-least-32-bytes-long-xxxxxxxx"
TENANT = uuid.uuid4()
CSRF = {"X-Requested-With": "predictax"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setattr(identity, "_login_throttle", LoginThrottle(max_failures=5))
    monkeypatch.setattr(identity.audit, "record", lambda *a, **k: audits.append((a, k)))
    audits.clear()


audits: list = []


def _tokens(app_metadata: dict, email: str = "someone@example.com") -> dict:
    claims = {"sub": str(uuid.uuid4()), "email": email, "aud": "authenticated", "exp": int(time.time()) + 600,
              "app_metadata": app_metadata}
    return {"access_token": jwt.encode(claims, SECRET, algorithm="HS256"), "refresh_token": "refresh-token"}


def _signs_in_as(monkeypatch, app_metadata: dict, email: str = "someone@example.com", tenant_status: str = "active"):
    monkeypatch.setattr(auth_client, "sign_in", lambda e, p: _tokens(app_metadata, email))

    def load(tenant_id):
        if tenant_status != "active":
            raise AuthError("Your organisation's account is suspended. Contact support.")
        return types.SimpleNamespace(id=tenant_id, name="Acme Motors", config={"currency": "EUR"})
    monkeypatch.setattr(identity, "load_active_tenant", load)


# ── the service ─────────────────────────────────────────────────────────────

def test_a_customer_account_gets_a_customer_session(monkeypatch):
    _signs_in_as(monkeypatch, {"tenant_id": str(TENANT), "role": "tenant_admin"}, "boss@acme.example")
    result = identity.sign_in("boss@acme.example", "pw")
    assert result.kind == "customer" and result.operator is None
    assert result.customer.identity.tenant_id == TENANT and result.customer.tenant_name == "Acme Motors"


def test_an_operator_account_gets_an_operator_session_and_the_sign_in_is_audited(monkeypatch):
    _signs_in_as(monkeypatch, {"role": "platform_admin"}, "owner@predictax.example")
    result = identity.sign_in("owner@predictax.example", "pw")
    assert result.kind == "operator" and result.customer is None
    assert result.operator.operator.email == "owner@predictax.example"
    assert len(audits) == 1 and audits[0][0] == ("operator.sign_in",) and audits[0][1] == {"actor": "owner@predictax.example"}


def test_a_customer_sign_in_is_not_written_to_the_operator_audit_trail(monkeypatch):
    _signs_in_as(monkeypatch, {"tenant_id": str(TENANT), "role": "tenant_user"})
    identity.sign_in("someone@example.com", "pw")
    assert audits == []


def test_an_operator_pinned_to_a_tenant_is_refused(monkeypatch):
    """platform_admin AND a tenant is contradictory: refuse rather than guess which one was meant."""
    _signs_in_as(monkeypatch, {"role": "platform_admin", "tenant_id": str(TENANT)})
    with pytest.raises(AuthError, match="not set up correctly"):
        identity.sign_in("x@example.com", "pw")


def test_an_account_with_neither_role_nor_tenant_is_refused(monkeypatch):
    _signs_in_as(monkeypatch, {})
    with pytest.raises(AuthError, match="not linked"):
        identity.sign_in("x@example.com", "pw")


def test_user_metadata_cannot_make_an_account_an_operator(monkeypatch):
    """Only app_metadata counts. A user-editable field claiming platform_admin changes nothing."""
    claims = {"sub": "u", "aud": "authenticated", "exp": int(time.time()) + 600, "app_metadata": {},
              "user_metadata": {"role": "platform_admin"}}
    monkeypatch.setattr(auth_client, "sign_in", lambda e, p: {"access_token": jwt.encode(claims, SECRET, algorithm="HS256")})
    with pytest.raises(AuthError, match="not linked"):
        identity.sign_in("x@example.com", "pw")


def test_a_suspended_organisation_cannot_sign_in(monkeypatch):
    _signs_in_as(monkeypatch, {"tenant_id": str(TENANT), "role": "tenant_user"}, tenant_status="suspended")
    with pytest.raises(AuthError, match="suspended"):
        identity.sign_in("x@example.com", "pw")


def test_wrong_passwords_lock_the_address_out_whatever_kind_it_is(monkeypatch):
    monkeypatch.setattr(auth_client, "sign_in", lambda e, p: (_ for _ in ()).throw(AuthError("Invalid email or password.")))
    for _ in range(5):
        with pytest.raises(AuthError, match="Invalid email or password"):
            identity.sign_in("victim@example.com", "guess")
    _signs_in_as(monkeypatch, {"role": "platform_admin"}, "victim@example.com")
    with pytest.raises(AuthError, match="Too many failed attempts"):
        identity.sign_in("victim@example.com", "the-right-password")


def test_a_failed_sign_in_reveals_nothing_about_the_kind_of_account(monkeypatch):
    """Same message for an unknown address and a wrong password, and it is written to no audit trail."""
    monkeypatch.setattr(auth_client, "sign_in", lambda e, p: (_ for _ in ()).throw(AuthError("Invalid email or password.")))
    with pytest.raises(AuthError) as unknown:
        identity.sign_in("nobody@example.com", "pw")
    assert str(unknown.value) == "Invalid email or password." and audits == []


# ── the endpoint: cookies and the response ──────────────────────────────────

@pytest.fixture()
def client():
    from backend.api.app import app
    return TestClient(app)


def _cookie_names(response) -> set[str]:
    """Names of the cookies the response SETS with a live value (a delete is sent as an empty value)."""
    return {c.split("=", 1)[0] for c in response.headers.get_list("set-cookie") if not c.split(";", 1)[0].endswith("=\"\"")
            and c.split(";", 1)[0].split("=", 1)[1] != ""}


def _deleted_cookie_names(response) -> set[str]:
    return {c.split("=", 1)[0] for c in response.headers.get_list("set-cookie") if "Max-Age=0" in c or 'expires=Thu, 01 Jan 1970' in c}


def test_the_form_sends_a_customer_to_the_customer_app_with_customer_cookies_only(client, monkeypatch):
    _signs_in_as(monkeypatch, {"tenant_id": str(TENANT), "role": "tenant_admin"}, "boss@acme.example")
    r = client.post("/api/auth/login", json={"email": "boss@acme.example", "password": "pw"}, headers=CSRF)
    assert r.status_code == 200
    assert r.json() == {"kind": "customer", "email": "boss@acme.example", "organisation": "Acme Motors"}
    assert cookies.ACCESS_COOKIE in _cookie_names(r) and cookies.ADMIN_ACCESS_COOKIE not in _cookie_names(r)
    assert cookies.ADMIN_ACCESS_COOKIE in _deleted_cookie_names(r)          # never left holding both kinds


def test_the_form_sends_an_operator_to_the_admin_console_with_operator_cookies_only(client, monkeypatch):
    _signs_in_as(monkeypatch, {"role": "platform_admin"}, "owner@predictax.example")
    r = client.post("/api/auth/login", json={"email": "owner@predictax.example", "password": "pw"}, headers=CSRF)
    assert r.status_code == 200
    assert r.json() == {"kind": "operator", "email": "owner@predictax.example", "organisation": None}
    assert cookies.ADMIN_ACCESS_COOKIE in _cookie_names(r) and cookies.ACCESS_COOKIE not in _cookie_names(r)
    assert cookies.ACCESS_COOKIE in _deleted_cookie_names(r)


def test_bad_credentials_get_a_401_and_no_cookies(client, monkeypatch):
    monkeypatch.setattr(auth_client, "sign_in", lambda e, p: (_ for _ in ()).throw(AuthError("Invalid email or password.")))
    r = client.post("/api/auth/login", json={"email": "a@b.co", "password": "nope"}, headers=CSRF)
    assert r.status_code == 401 and r.json() == {"detail": "Invalid email or password."}
    assert _cookie_names(r) == set()


def test_the_form_still_needs_the_csrf_header(client):
    assert client.post("/api/auth/login", json={"email": "a@b.co", "password": "pw"}).status_code == 403


def test_the_customer_only_endpoint_still_refuses_operators(client, monkeypatch):
    """Clients that must never receive an operator session can keep using the customer-only sign-in."""
    _signs_in_as(monkeypatch, {"role": "platform_admin"}, "owner@predictax.example")
    monkeypatch.setattr(identity, "_customer_throttle", LoginThrottle())
    r = client.post("/api/auth/login/customer", json={"email": "owner@predictax.example", "password": "pw"}, headers=CSRF)
    assert r.status_code == 401
    assert cookies.ACCESS_COOKIE not in _cookie_names(r) and cookies.ADMIN_ACCESS_COOKIE not in _cookie_names(r)
