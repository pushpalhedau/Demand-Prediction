"""
The admin (operator) HTTP API end to end: real logins against the local auth server, real accounts in Postgres.
    docker compose up -d db auth
"""
import os
import time
import uuid

import pytest
import requests
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.auth import client as auth_client
from backend.core.config import get_settings
from backend.tenancy.provision import create_operator, get_tenant_id

CSRF = {"X-Requested-With": "predictax"}


def _up() -> bool:
    base = os.getenv("AUTH_BASE_URL")
    try:
        return bool(base) and requests.get(f"{base}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


pytestmark = pytest.mark.skipif(not _up(), reason="auth server not available")


def _client() -> TestClient:
    return TestClient(app, base_url="http://testserver")


@pytest.fixture
def operator_login():
    email = f"op-{uuid.uuid4().hex[:8]}@example.com"
    password = f"Pw-{uuid.uuid4().hex[:10]}"
    created = create_operator(email, password)
    yield {"email": created["email"], "password": password}
    for u in auth_client.admin_list_users():
        if u["email"] == email:
            auth_client.admin_delete_user(u["id"])


@pytest.fixture
def operator_client(operator_login) -> TestClient:
    c = _client()
    r = c.post("/api/admin/auth/login", json={"email": operator_login["email"], "password": operator_login["password"]}, headers=CSRF)
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def account(operator_client: TestClient):
    """A throwaway customer account, created and torn down for one test."""
    name = f"Test Motors {uuid.uuid4().hex[:6]}"
    body = {"name": name, "admin_email": f"acct-{uuid.uuid4().hex[:8]}@example.com",
            "config": {"currency": "USD", "language": "en", "region_label": "State"}}
    r = operator_client.post("/api/admin/accounts", json=body, headers=CSRF)
    assert r.status_code == 201, r.text
    created = r.json()
    yield {"name": name, **created}
    tenant_id = get_tenant_id(created["slug"])
    if tenant_id:
        for u in auth_client.users_of_tenant(tenant_id):
            auth_client.admin_delete_user(u["id"])
        from backend.db.connection import get_admin_session
        from backend.db.models import Tenant
        db = get_admin_session()
        db.query(Tenant).filter(Tenant.id == tenant_id).delete()
        db.commit()
        db.close()


def test_admin_endpoints_refuse_anonymous_and_customer_callers(account):
    """A signed-out caller, and a customer token, are both refused the same way."""
    anon = _client()
    for path in ("/api/admin/auth/me", "/api/admin/accounts", f"/api/admin/accounts/{account['slug']}", "/api/admin/audit"):
        assert anon.get(path).status_code == 401, path

    customer = _client()
    r = customer.post("/api/auth/login", json={"email": account["email"], "password": account["password"]}, headers=CSRF)
    assert r.status_code == 200, r.text
    assert customer.get("/api/admin/accounts").status_code == 401


def test_admin_login_uses_its_own_cookies_not_the_customer_ones(operator_client: TestClient):
    assert "px_admin_access" in operator_client.cookies
    assert "px_access" not in operator_client.cookies


def test_state_changing_admin_requests_need_the_csrf_header(operator_login):
    r = _client().post("/api/admin/auth/login", json=operator_login)
    assert r.status_code == 403


def test_account_lifecycle(operator_client: TestClient, account):
    slug = account["slug"]

    got = operator_client.get(f"/api/admin/accounts/{slug}")
    assert got.status_code == 200
    detail = got.json()
    assert detail["status"] == "active" and detail["summary"]["sales"] == 0 and detail["summary"]["models"] is False

    listed = operator_client.get("/api/admin/accounts").json()
    assert any(a["slug"] == slug for a in listed)

    updated = operator_client.patch(f"/api/admin/accounts/{slug}/settings", json={"currency": "EUR"}, headers=CSRF)
    assert updated.status_code == 200 and updated.json()["currency"] == "EUR"

    added = operator_client.post(f"/api/admin/accounts/{slug}/logins", json={"email": f"user-{uuid.uuid4().hex[:6]}@example.com", "role": "tenant_user"}, headers=CSRF)
    assert added.status_code == 201 and added.json()["password"]
    logins = operator_client.get(f"/api/admin/accounts/{slug}/logins").json()
    assert len(logins) == 2   # the first admin plus the one just added

    reset = operator_client.post(f"/api/admin/accounts/logins/{logins[0]['id']}/reset-password", headers=CSRF)
    assert reset.status_code == 200 and reset.json()["password"]

    suspended = operator_client.post(f"/api/admin/accounts/{slug}/status", json={"status": "suspended"}, headers=CSRF)
    assert suspended.status_code == 200
    assert operator_client.get(f"/api/admin/accounts/{slug}").json()["status"] == "suspended"
    reactivated = operator_client.post(f"/api/admin/accounts/{slug}/status", json={"status": "active"}, headers=CSRF)
    assert reactivated.status_code == 200


def test_unknown_account_is_404_not_a_leak(operator_client: TestClient):
    r = operator_client.get("/api/admin/accounts/no-such-account-at-all")
    assert r.status_code == 404


@pytest.mark.parametrize("body", [
    {"name": "", "admin_email": "a@b.co"},
    {"name": "X", "admin_email": "a@b.co", "config": {"language": "fr"}},
    {"name": "X", "admin_email": "a@b.co", "config": {"symbol_position": "middle"}},
])
def test_create_account_rejects_invalid_input(operator_client: TestClient, body):
    assert operator_client.post("/api/admin/accounts", json=body, headers=CSRF).status_code == 422


def test_actions_are_attributed_to_the_signed_in_operator(operator_client: TestClient, account, operator_login):
    operator_client.patch(f"/api/admin/accounts/{account['slug']}/settings", json={"currency": "GBP"}, headers=CSRF)
    events = operator_client.get("/api/admin/audit", params={"account": account["slug"], "limit": 5}).json()
    assert any(e["actor"] == operator_login["email"] and e["action"] == "account.settings" for e in events)


def test_retrain_starts_a_trackable_job(operator_client: TestClient, account):
    started = operator_client.post(f"/api/admin/accounts/{account['slug']}/retrain", headers=CSRF)
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    status = operator_client.get(f"/api/admin/accounts/{account['slug']}/jobs/{job_id}")
    assert status.status_code == 200 and status.json()["status"] in ("queued", "running", "failed", "succeeded")
    assert operator_client.get(f"/api/admin/accounts/{account['slug']}/jobs/{uuid.uuid4()}").status_code == 404


def test_import_schema_lists_the_field_catalog(operator_client: TestClient):
    body = operator_client.get("/api/admin/imports/schema").json()
    assert "sales" in body["load_order"] and "sales" in body["required_tables"]
    assert any(f["name"] == "sale_date" for f in body["tables"]["sales"])


def test_import_wizard_full_flow(operator_client: TestClient, account):
    """Upload -> mapping proposal -> dry-run -> start -> poll to completion, exactly what the wizard UI drives."""
    slug = account["slug"]
    job_id = str(uuid.uuid4())
    csv_body = b"sale_date,selling_price\n2025-01-01,100\n2025-01-02,200\n"

    up = operator_client.post(f"/api/admin/accounts/{slug}/imports/{job_id}/files/sales",
                              files={"file": ("sales.csv", csv_body, "text/csv")}, headers=CSRF)
    assert up.status_code == 204, up.text

    mapping_resp = operator_client.get(f"/api/admin/accounts/{slug}/imports/{job_id}/sales/mapping")
    assert mapping_resp.status_code == 200, mapping_resp.text
    proposal = mapping_resp.json()
    assert proposal["columns"] == ["sale_date", "selling_price"]
    assert proposal["proposal"]["sale_date"]["source"] == "sale_date"
    assert proposal["saved"] is None

    mapping = {"columns": {name: {"source": c["source"], "transform": c["transform"]}
                            for name, c in proposal["proposal"].items()}, "extras": True}

    dry = operator_client.post(f"/api/admin/accounts/{slug}/imports/{job_id}/sales/dry-run",
                               json={"mapping": mapping, "units": {"distance": "km"}, "dayfirst": False, "decimal": "."},
                               headers=CSRF)
    assert dry.status_code == 200, dry.text
    assert dry.json()["rows_out"] == 2

    start = operator_client.post(f"/api/admin/accounts/{slug}/imports/{job_id}/start",
                                 json={"tables": ["sales"], "mappings": {"sales": mapping}, "units": {"distance": "km"},
                                       "dayfirst": False, "decimal": ".", "replace": True, "train": False},
                                 headers=CSRF)
    assert start.status_code == 202, start.text
    assert start.json()["job_id"] == job_id

    job = None
    for _ in range(30):
        job = operator_client.get(f"/api/admin/accounts/{slug}/jobs/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            break
        time.sleep(0.5)
    assert job["status"] == "succeeded", job

    assert operator_client.post(f"/api/admin/accounts/{slug}/imports/{job_id}/done", headers=CSRF).status_code == 204
    detail = operator_client.get(f"/api/admin/accounts/{slug}").json()
    assert detail["summary"]["sales"] == 2


def test_import_wizard_rejects_starting_without_an_upload(operator_client: TestClient, account):
    job_id = str(uuid.uuid4())
    r = operator_client.post(f"/api/admin/accounts/{account['slug']}/imports/{job_id}/start",
                             json={"tables": ["sales"], "mappings": {}, "replace": True, "train": False}, headers=CSRF)
    assert r.status_code == 422


def _upload_sales(client: TestClient, slug: str, job_id: str):
    return client.post(f"/api/admin/accounts/{slug}/imports/{job_id}/files/sales",
                       files={"file": ("sales.csv", b"sale_date,selling_price\n2025-01-01,100\n", "text/csv")}, headers=CSRF)


def test_import_endpoints_refuse_anonymous_and_customer_callers(account):
    job_id = str(uuid.uuid4())
    anon = _client()
    assert anon.get("/api/admin/imports/schema").status_code == 401
    assert _upload_sales(anon, account["slug"], job_id).status_code == 401
    assert anon.get(f"/api/admin/accounts/{account['slug']}/imports/{job_id}/sales/mapping").status_code == 401

    customer = _client()
    r = customer.post("/api/auth/login", json={"email": account["email"], "password": account["password"]}, headers=CSRF)
    assert r.status_code == 200, r.text
    assert customer.get("/api/admin/imports/schema").status_code == 401
    assert _upload_sales(customer, account["slug"], job_id).status_code == 401


def test_import_endpoints_reject_malformed_ids_and_tables(operator_client: TestClient, account):
    slug = account["slug"]
    assert _upload_sales(operator_client, slug, "../../etc/passwd").status_code in (404, 422)
    assert _upload_sales(operator_client, slug, "not-a-uuid").status_code == 422
    bad_table = operator_client.post(f"/api/admin/accounts/{slug}/imports/{uuid.uuid4()}/files/users",
                                     files={"file": ("x.csv", b"a\n1\n", "text/csv")}, headers=CSRF)
    assert bad_table.status_code == 422


def test_import_files_are_scoped_to_their_own_account(operator_client: TestClient, account):
    """A file uploaded under one account must not be readable through another account's wizard session."""
    other = operator_client.post("/api/admin/accounts", headers=CSRF, json={
        "name": f"Other {uuid.uuid4().hex[:6]}", "admin_email": f"o-{uuid.uuid4().hex[:8]}@example.com"}).json()
    try:
        job_id = str(uuid.uuid4())
        assert _upload_sales(operator_client, account["slug"], job_id).status_code == 204
        assert operator_client.get(f"/api/admin/accounts/{account['slug']}/imports/{job_id}/sales/mapping").status_code == 200
        assert operator_client.get(f"/api/admin/accounts/{other['slug']}/imports/{job_id}/sales/mapping").status_code == 422
    finally:
        operator_client.post(f"/api/admin/accounts/{other['slug']}/delete", json={"confirm": other["slug"]}, headers=CSRF)


def test_deleting_an_account_requires_the_typed_slug(operator_client: TestClient, account):
    slug = account["slug"]
    assert operator_client.post(f"/api/admin/accounts/{slug}/delete", json={"confirm": "nope"}, headers=CSRF).status_code == 422
    assert operator_client.post(f"/api/admin/accounts/{slug}/delete", json={}, headers=CSRF).status_code == 422
    assert operator_client.get(f"/api/admin/accounts/{slug}").status_code == 200
    anon = _client()
    assert anon.post(f"/api/admin/accounts/{slug}/delete", json={"confirm": slug}, headers=CSRF).status_code == 401


def test_deleting_an_account_removes_everything_it_owned(operator_client: TestClient):
    created = operator_client.post("/api/admin/accounts", headers=CSRF, json={
        "name": f"Doomed {uuid.uuid4().hex[:6]}", "admin_email": f"d-{uuid.uuid4().hex[:8]}@example.com"}).json()
    slug = created["slug"]
    job_id = str(uuid.uuid4())
    assert _upload_sales(operator_client, slug, job_id).status_code == 204
    tenant_id = get_tenant_id(slug)
    upload_folder = get_settings().upload_dir / str(tenant_id)
    assert upload_folder.exists()

    r = operator_client.post(f"/api/admin/accounts/{slug}/delete", json={"confirm": slug}, headers=CSRF)
    assert r.status_code == 200 and r.json() == {"logins": 1}

    assert operator_client.get(f"/api/admin/accounts/{slug}").status_code == 404
    assert not upload_folder.exists()
    assert auth_client.users_of_tenant(tenant_id) == []
    events = operator_client.get("/api/admin/audit", params={"account": slug, "limit": 5}).json()
    assert any(e["action"] == "account.delete" for e in events)
    assert operator_client.post(f"/api/admin/accounts/{slug}/delete", json={"confirm": slug}, headers=CSRF).status_code == 404
