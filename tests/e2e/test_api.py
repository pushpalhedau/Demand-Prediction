"""
The HTTP API end to end: real logins against the local auth server, real demo tenants in Postgres.
    docker compose up -d db auth   (and the demo tenants loaded)
"""
import os
import uuid

import pytest
import requests
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.auth import client as auth_client
from backend.tenancy.provision import add_user, get_tenant_id

CSRF = {"X-Requested-With": "predictax"}
DEMOS = ("germany-demo", "uae-demo")


def _up() -> bool:
    base = os.getenv("AUTH_BASE_URL")
    try:
        return bool(base) and requests.get(f"{base}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


def _demo_loaded() -> bool:
    try:
        return all(get_tenant_id(s) for s in DEMOS)
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not (_up() and _demo_loaded()), reason="auth server or demo tenants not available")


@pytest.fixture(scope="module")
def logins():
    made = {}
    for slug in DEMOS:
        made[slug] = add_user(slug, f"api-{uuid.uuid4().hex[:8]}@example.com", f"Pw-{uuid.uuid4().hex[:10]}", "tenant_user")
    yield made
    for slug, r in made.items():
        for u in auth_client.users_of_tenant(get_tenant_id(slug)):
            if u["email"] == r["email"]:
                auth_client.admin_delete_user(u["id"])


def _client() -> TestClient:
    return TestClient(app, base_url="http://testserver")


def _sign_in(login) -> TestClient:
    c = _client()
    r = c.post("/api/auth/login", json={"email": login["email"], "password": login["password"]}, headers=CSRF)
    assert r.status_code == 200, r.text
    return c


def test_endpoints_refuse_anonymous_callers():
    c = _client()
    for path in ("/api/me", "/api/workspace/filters", "/api/overview/glance", "/api/overview/recommendations"):
        assert c.get(path).status_code == 401, path


def test_state_changing_requests_need_the_csrf_header(logins):
    r = _client().post("/api/auth/login", json={"email": "a@b.co", "password": "x"})
    assert r.status_code == 403


def test_wrong_password_is_a_401_without_detail_about_which_part(logins):
    login = next(iter(logins.values()))
    r = _client().post("/api/auth/login", json={"email": login["email"], "password": "nope"}, headers=CSRF)
    assert r.status_code == 401 and r.json()["detail"] == "Invalid email or password."


def test_session_cookies_are_httponly_and_strict(logins):
    login = next(iter(logins.values()))
    r = _client().post("/api/auth/login", json={"email": login["email"], "password": login["password"]}, headers=CSRF)
    cookies = r.headers.get_list("set-cookie")
    assert len(cookies) == 2
    for c in cookies:
        assert "HttpOnly" in c and "SameSite=strict" in c
    assert "access_token" not in r.text            # tokens are never in the body


def test_a_forged_token_is_refused(logins):
    c = _client()
    c.cookies.set("px_access", "not.a.jwt")
    assert c.get("/api/me").status_code == 401


def test_each_customer_only_gets_their_own_tenant(logins):
    seen = {}
    for slug, login in logins.items():
        c = _sign_in(login)
        me = c.get("/api/me").json()
        glance = c.get("/api/overview/glance").json()
        seen[slug] = (me["organisation"]["currency"], glance["kpis"]["total_revenue"], me["tabs"])
        assert me["ready"] and "tab.overview" in me["tabs"]
        assert glance["trend"]["revenue"] and glance["by_category"]
    assert seen["germany-demo"][0] == "EUR" and seen["uae-demo"][0] == "AED"
    assert seen["germany-demo"][1] != seen["uae-demo"][1]


def test_filters_narrow_the_numbers_and_bad_input_is_rejected(logins):
    c = _sign_in(logins["germany-demo"])
    everything = c.get("/api/overview/glance").json()["kpis"]["total_sales"]
    regions = c.get("/api/workspace/filters").json()["regions"]
    one = c.get("/api/overview/glance", params={"region": regions[0]}).json()["kpis"]["total_sales"]
    assert 0 < one < everything
    assert c.get("/api/overview/glance", params={"start_date": "not-a-date"}).status_code == 422
    assert c.get("/api/overview/glance", params={"region": "x" * 500}).status_code == 422


def test_recommendations_carry_the_plays(logins):
    c = _sign_in(logins["uae-demo"])
    body = c.get("/api/overview/recommendations").json()
    assert body["plays"] and {"title", "detail", "impact_amt", "confidence", "accent"} <= set(body["plays"][0])


def test_logout_ends_the_session(logins):
    c = _sign_in(next(iter(logins.values())))
    assert c.get("/api/me").status_code == 200
    assert c.post("/api/auth/logout", headers=CSRF).status_code == 204
    assert c.get("/api/me").status_code == 401


def test_a_customer_login_cannot_reach_a_context_left_by_a_previous_request(logins):
    """Requests alternate between two tenants on the same worker threads: no scope may leak across them."""
    a, b = _sign_in(logins["germany-demo"]), _sign_in(logins["uae-demo"])
    for _ in range(6):
        assert a.get("/api/me").json()["organisation"]["currency"] == "EUR"
        assert b.get("/api/me").json()["organisation"]["currency"] == "AED"
