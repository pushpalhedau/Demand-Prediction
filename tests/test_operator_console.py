"""
Admin console: operator login, account creation, per-account screens.
Needs the local auth server (docker compose up -d db auth); skipped otherwise.
"""
import os
import time
import uuid

import pytest
import requests
from sqlalchemy.exc import NoResultFound
from streamlit.testing.v1 import AppTest

from backend.auth import client as auth_client
from backend.auth.client import AuthError, Operator
from backend.db.connection import get_admin_session, init_all_tables
from backend.db.models import Tenant
from backend.ingestion.jobs import create_job, get_job, process_job
from backend.services.identity import load_active_tenant as _load_active_tenant
from backend.tenancy.provision import create_operator, create_tenant, get_tenant, set_status


def _auth_up() -> bool:
    base = os.getenv("AUTH_BASE_URL")
    try:
        return bool(base) and requests.get(f"{base}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


pytestmark = pytest.mark.skipif(not _auth_up(), reason="local auth server is not running")


def _delete_tenant_and_users(tenant_id):
    for u in auth_client.users_of_tenant(tenant_id):
        auth_client.admin_delete_user(u["id"])
    db = get_admin_session()
    db.query(Tenant).filter(Tenant.id == tenant_id).delete()
    db.commit()
    db.close()


@pytest.fixture(scope="module")
def operator():
    init_all_tables()
    email = f"op-{uuid.uuid4().hex[:8]}@example.com"
    r = create_operator(email, "Operator-Pw-2026!")
    yield r
    for u in auth_client.admin_list_users():
        if u["email"] == email:
            auth_client.admin_delete_user(u["id"])


@pytest.fixture
def account():
    init_all_tables()
    slug = f"acct-{uuid.uuid4().hex[:8]}"
    r = create_tenant(slug, "Console Test Motors", f"{slug}@example.com", "Cust-Pw-2026!",
                      config={"currency": "GBP", "currency_symbol": "£", "language": "en"})
    yield r
    _delete_tenant_and_users(uuid.UUID(r["tenant_id"]))


def _console(slug=None):
    at = AppTest.from_file("frontend/admin_console/main.py", default_timeout=120)
    at.session_state["operator"] = Operator("op-1", "operator@example.com")
    at.session_state["op_refresh"] = "x"
    at.session_state["op_exp"] = time.time() + 3600
    if slug:
        at.session_state["selected_slug"] = slug
    return at


# ── who can get in ──────────────────────────────────────────────────────────

def test_operator_signs_in_and_is_recognised(operator):
    tokens = auth_client.sign_in(operator["email"], operator["password"])
    op = auth_client.operator_from_claims(auth_client.verify_access_token(tokens["access_token"]))
    assert op.email == operator["email"]


def test_an_operator_login_cannot_open_a_customer_dashboard(operator):
    tokens = auth_client.sign_in(operator["email"], operator["password"])
    claims = auth_client.verify_access_token(tokens["access_token"])
    with pytest.raises(AuthError, match="not linked to an organisation"):
        auth_client.identity_from_claims(claims)


def test_a_customer_login_cannot_open_the_console(account):
    tokens = auth_client.sign_in(account["email"], account["password"])
    with pytest.raises(AuthError, match="cannot use the admin console"):
        auth_client.operator_from_claims(auth_client.verify_access_token(tokens["access_token"]))


def test_a_customer_cannot_become_an_operator_by_editing_their_own_metadata(account):
    tokens = auth_client.sign_in(account["email"], account["password"])
    requests.put(f"{os.getenv('AUTH_BASE_URL')}/user",
                 headers={"Authorization": f"Bearer {tokens['access_token']}", "Content-Type": "application/json"},
                 json={"data": {"role": "platform_admin"}}, timeout=10)
    tokens = auth_client.sign_in(account["email"], account["password"])
    with pytest.raises(AuthError):
        auth_client.operator_from_claims(auth_client.verify_access_token(tokens["access_token"]))


def test_console_shows_only_a_login_form_when_signed_out():
    at = AppTest.from_file("frontend/admin_console/main.py", default_timeout=60).run()
    assert not at.exception
    assert [t.label for t in at.text_input] == ["Email", "Password"]
    assert not at.sidebar.button


def test_console_login_accepts_an_operator_and_rejects_a_customer(operator, account):
    at = AppTest.from_file("frontend/admin_console/main.py", default_timeout=60).run()
    at.text_input[0].input(account["email"])
    at.text_input[1].input(account["password"])
    at.button[0].click().run()
    assert any("Invalid email or password" in e.value for e in at.error)
    assert "operator" not in at.session_state

    at.text_input[0].input(operator["email"])
    at.text_input[1].input(operator["password"])
    at.button[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["operator"].email == operator["email"]


# ── accounts ────────────────────────────────────────────────────────────────

def test_accounts_page_lists_accounts_and_offers_creation(account):
    at = _console().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Accounts" in m.value for m in at.markdown)
    assert any(e.label == "Create a new account" for e in at.expander)


def test_creating_an_account_through_the_form_makes_a_working_login(operator):
    at = _console().run()
    values = {"Account name": "Form Made Motors", "Short id (letters, digits, hyphens)": f"form-{uuid.uuid4().hex[:6]}",
              "First admin's email": f"form-{uuid.uuid4().hex[:6]}@example.com",
              "Password (leave blank to generate one)": "Form-Pw-2026!", "Currency code": "GBP",
              "Country (for local news)": "United Kingdom"}
    for ti in at.text_input:
        if ti.label in values:
            ti.input(values[ti.label])
    at.text_input(key=None) if False else None
    [b for b in at.button if b.label == "Create account"][0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    slug = values["Short id (letters, digits, hyphens)"]
    try:
        t = get_tenant(slug)
        assert t["config"]["currency"] == "GBP" and t["config"]["currency_symbol"] == "£"
        assert at.session_state["selected_slug"] == slug
        tokens = auth_client.sign_in(values["First admin's email"], values["Password (leave blank to generate one)"])
        ident = auth_client.identity_from_claims(auth_client.verify_access_token(tokens["access_token"]))
        assert str(ident.tenant_id) == str(t["id"]) and ident.role == "tenant_admin"
    finally:
        _delete_tenant_and_users(get_tenant(slug)["id"])


def test_a_bad_setting_is_rejected_and_creates_nothing(operator):
    at = _console().run()
    slug = f"bad-{uuid.uuid4().hex[:6]}"
    values = {"Account name": "Bad Motors", "Short id (letters, digits, hyphens)": slug,
              "First admin's email": f"{slug}@example.com", "Currency code": "GBP"}
    for ti in at.text_input:
        if ti.label in values:
            ti.input(values[ti.label])
        if ti.label == "Symbol (blank = automatic)":
            ti.input("<script>")
    [b for b in at.button if b.label == "Create account"][0].click().run()
    assert any("Invalid value" in e.value for e in at.error)
    with pytest.raises(NoResultFound):
        get_tenant(slug)


# ── one account ─────────────────────────────────────────────────────────────

def test_account_screen_renders_with_all_its_tabs(account):
    at = _console(account["slug"]).run()
    assert not at.exception, [e.value for e in at.exception]
    assert [t.label for t in at.tabs] == ["Import data", "History & models", "Logins", "Settings", "Access"]
    assert any("No data yet" in w.value for w in at.warning)


def test_logins_tab_lists_the_accounts_users(account):
    at = _console(account["slug"]).run()
    assert not at.exception
    assert any(account["email"] in str(df.value) for df in at.dataframe)


def test_suspending_locks_the_account_out_and_reactivating_restores_it(account):
    tid = uuid.UUID(account["tenant_id"])
    _load_active_tenant(tid)                                      # active: fine
    set_status(account["slug"], "suspended")
    with pytest.raises(AuthError, match="suspended"):
        _load_active_tenant(tid)
    set_status(account["slug"], "active")
    _load_active_tenant(tid)


def test_retrain_only_job_runs_without_needing_any_files(account):
    tid = uuid.UUID(account["tenant_id"])
    jid = uuid.uuid4()
    create_job(tid, {"train_only": True, "train": True}, created_by="operator@example.com", job_id=jid)
    process_job(tid, jid)
    job = get_job(tid, jid)
    assert job["status"] == "succeeded"          # no data yet: models are skipped with a note, not a failure


def test_settings_change_reaches_the_customer(account):
    from backend.tenancy.provision import set_config
    set_config(account["slug"], {"region_label": "County"})
    assert _load_active_tenant(uuid.UUID(account["tenant_id"])).config["region_label"] == "County"
