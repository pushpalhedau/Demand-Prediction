"""
Real login flow against the local Supabase Auth (GoTrue) container:
  docker compose up -d db auth
Skipped when it is not running.
"""
import os
import uuid

import pytest
import requests

from auth import supabase
from auth.supabase import AuthError
from database.connection import get_admin_session, init_all_tables
from database.models import Tenant
from tenancy.provision import create_tenant


def _auth_up() -> bool:
    base = os.getenv("AUTH_BASE_URL")
    if not base:
        return False
    try:
        return requests.get(f"{base}/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


pytestmark = pytest.mark.skipif(not _auth_up(), reason="local auth server is not running")


@pytest.fixture
def two_accounts():
    init_all_tables()
    made = []
    for label in ("a", "b"):
        slug = f"e2e-{label}-{uuid.uuid4().hex[:6]}"
        r = create_tenant(slug, f"E2E {label}", f"{slug}@example.com", admin_password=f"Pw-{uuid.uuid4().hex[:10]}")
        made.append((slug, r))
    yield made
    admin = get_admin_session()
    for _, r in made:
        admin.query(Tenant).filter(Tenant.id == uuid.UUID(r["tenant_id"])).delete()
    admin.commit()
    admin.close()


def test_login_resolves_to_the_accounts_own_tenant(two_accounts):
    for slug, r in two_accounts:
        tokens = supabase.sign_in(r["email"], r["password"])
        identity = supabase.identity_from_claims(supabase.verify_access_token(tokens["access_token"]))
        assert str(identity.tenant_id) == r["tenant_id"]
        assert identity.role == "tenant_admin"
        assert identity.email == r["email"]


def test_two_accounts_never_resolve_to_each_others_tenant(two_accounts):
    ids = set()
    for _, r in two_accounts:
        tokens = supabase.sign_in(r["email"], r["password"])
        ids.add(supabase.identity_from_claims(supabase.verify_access_token(tokens["access_token"])).tenant_id)
    assert len(ids) == 2


def test_wrong_password_is_rejected(two_accounts):
    _, r = two_accounts[0]
    with pytest.raises(AuthError, match="Invalid email or password"):
        supabase.sign_in(r["email"], "definitely-wrong")


def test_refresh_token_issues_a_new_valid_session(two_accounts):
    _, r = two_accounts[0]
    tokens = supabase.sign_in(r["email"], r["password"])
    fresh = supabase.refresh(tokens["refresh_token"])
    ident = supabase.identity_from_claims(supabase.verify_access_token(fresh["access_token"]))
    assert str(ident.tenant_id) == r["tenant_id"]


def test_a_user_cannot_change_their_own_tenant_via_user_metadata(two_accounts):
    """user_metadata is user-writable; app_metadata (where tenant_id lives) is not."""
    _, ra = two_accounts[0]
    _, rb = two_accounts[1]
    tokens = supabase.sign_in(ra["email"], ra["password"])
    requests.put(f"{os.getenv('AUTH_BASE_URL')}/user",
                 headers={"Authorization": f"Bearer {tokens['access_token']}", "Content-Type": "application/json"},
                 json={"data": {"tenant_id": rb["tenant_id"]}}, timeout=10)
    tokens = supabase.sign_in(ra["email"], ra["password"])
    ident = supabase.identity_from_claims(supabase.verify_access_token(tokens["access_token"]))
    assert str(ident.tenant_id) == ra["tenant_id"]
