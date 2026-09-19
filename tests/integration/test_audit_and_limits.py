import io
import os
import time
import uuid

import pytest
import requests
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from streamlit.testing.v1 import AppTest

from backend.auth import client as auth_client
from backend.core.errors import AuthError, IngestError
from backend.core.request_context import bind_actor, clear_request, tenant_context
from backend.core.security import validate_password
from backend.db.connection import get_admin_session, get_db_session, init_all_tables
from backend.db.models import AuditEvent, Tenant
from backend.ingestion import pipeline
from backend.services import accounts as accounts_service
from backend.services import identity, imports
from backend.tenancy import audit
from backend.tenancy.provision import create_operator


def _auth_up() -> bool:
    base = os.getenv("AUTH_BASE_URL")
    try:
        return bool(base) and requests.get(f"{base}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


needs_auth = pytest.mark.skipif(not _auth_up(), reason="local auth server is not running")


@pytest.fixture(autouse=True)
def _db():
    init_all_tables()
    clear_request()
    yield
    clear_request()


def _events(action, since_id):
    db = get_admin_session()
    try:
        return db.query(AuditEvent).filter(AuditEvent.action == action, AuditEvent.id > since_id).all()
    finally:
        db.close()


def _last_id():
    db = get_admin_session()
    try:
        return db.query(AuditEvent.id).order_by(AuditEvent.id.desc()).limit(1).scalar() or 0
    finally:
        db.close()


# ── the audit trail itself ──────────────────────────────────────────────────

def test_events_are_recorded_with_the_bound_actor_and_secrets_are_stripped():
    before = _last_id()
    bind_actor("op@example.com")
    audit.record("test.action", tenant="acme", detail={"email": "a@b.c", "password": "hunter2", "token": "t"})
    (e,) = _events("test.action", before)
    assert e.actor == "op@example.com" and e.target_tenant == "acme" and e.outcome == "ok"
    assert e.detail == {"email": "a@b.c"}                       # password and token never stored


def test_the_trail_cannot_be_edited_or_deleted_even_by_the_owner_role():
    audit.record("test.immutable")
    db = get_admin_session()
    try:
        for sql in ("UPDATE audit_events SET actor = 'x'", "DELETE FROM audit_events", "TRUNCATE audit_events"):
            with pytest.raises((DBAPIError, ProgrammingError), match="append-only"):
                db.execute(text(sql))
            db.rollback()
    finally:
        db.close()


def test_the_customer_facing_role_cannot_read_or_write_the_trail():
    audit.record("test.hidden")
    with tenant_context(uuid.uuid4()):
        s = get_db_session()
        try:
            for sql in ("SELECT count(*) FROM audit_events", "INSERT INTO audit_events (actor, action, outcome) VALUES ('x','y','ok')"):
                with pytest.raises((DBAPIError, ProgrammingError), match="permission denied"):
                    s.execute(text(sql))
                s.rollback()
        finally:
            s.close()


def test_a_failure_to_write_the_trail_never_blocks_the_action(monkeypatch):
    monkeypatch.setattr(audit, "get_admin_session", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    audit.record("test.no_db")                                 # must not raise


# ── operator actions are audited ────────────────────────────────────────────

@needs_auth
def test_operator_sign_in_success_and_failure_are_recorded():
    email = f"aud-{uuid.uuid4().hex[:8]}@example.com"
    create_operator(email, "Operator-Pw-2026!")
    try:
        before = _last_id()
        with pytest.raises(AuthError):
            identity.sign_in_operator(email, "wrong-password")
        identity.sign_in_operator(email, "Operator-Pw-2026!")
        events = [e for e in _events("operator.sign_in", before) if e.actor == email]
        assert sorted(e.outcome for e in events) == ["denied", "ok"]
    finally:
        for u in auth_client.admin_list_users():
            if u["email"] == email:
                auth_client.admin_delete_user(u["id"])


@needs_auth
def test_creating_an_account_is_audited_and_a_weak_password_is_refused():
    slug = f"aud-{uuid.uuid4().hex[:8]}"
    with pytest.raises(AuthError, match="at least"):
        accounts_service.create_account("Weak", slug, f"{slug}@example.com", "short", {"currency": "GBP"})
    before = _last_id()
    bind_actor("op@example.com")
    created = accounts_service.create_account("Audited Motors", slug, f"{slug}@example.com", "Strong-Pw-2026!", {"currency": "GBP"})
    try:
        (e,) = _events("account.create", before)
        assert e.target_tenant == slug and e.actor == "op@example.com"
        assert "Strong-Pw" not in str(e.detail)
    finally:
        for u in auth_client.users_of_tenant(created["tenant_id"]):
            auth_client.admin_delete_user(u["id"])
        db = get_admin_session()
        db.query(Tenant).filter(Tenant.slug == slug).delete()
        db.commit()
        db.close()


def test_the_audit_screen_shows_recent_events():
    audit.record("test.visible", tenant="acme")
    from backend.auth.client import Operator
    at = AppTest.from_file("frontend/admin_console/main.py", default_timeout=60)
    at.session_state["operator"] = Operator("op-1", "op@example.com")
    at.session_state["op_refresh"] = "x"
    at.session_state["op_exp"] = time.time() + 3600
    at.session_state["admin_section"] = "Audit log"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("test.visible" in list(df.value["Action"]) for df in at.dataframe)


# ── password policy ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("pw", ["short", "aaaaaaaaaaaa", "1111111111", "password123"])
def test_weak_passwords_are_refused(pw):
    with pytest.raises(AuthError):
        validate_password(pw)


def test_a_reasonable_passphrase_is_accepted():
    validate_password("correct horse battery")


# ── upload limits ───────────────────────────────────────────────────────────

def test_an_oversized_upload_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    with pytest.raises(IngestError, match="larger than the 1 MB limit"):
        imports.save_upload(uuid.uuid4(), str(uuid.uuid4()), "sales", b"x" * (2 * 1024 * 1024))
    imports.save_upload(uuid.uuid4(), str(uuid.uuid4()), "sales", b"a,b\n1,2\n")       # small files are fine


def test_a_file_with_too_many_columns_is_refused(monkeypatch):
    monkeypatch.setattr(pipeline, "MAX_COLUMNS", 3)
    with pytest.raises(IngestError, match="columns"):
        pipeline.read_csv(io.StringIO("a,b,c,d\n1,2,3,4\n"))


def test_a_file_with_too_many_rows_is_refused(monkeypatch):
    monkeypatch.setattr(pipeline, "MAX_ROWS", 2)
    with pytest.raises(IngestError, match="rows"):
        pipeline.read_csv(io.StringIO("a,b\n1,2\n3,4\n5,6\n"))
    assert len(pipeline.read_csv(io.StringIO("a,b\n1,2\n"))) == 1
