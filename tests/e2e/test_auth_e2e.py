"""
Real login flow against the auth server and database configured in .env.
Skipped when the auth server is not reachable.
"""
import os
import uuid

import pytest
import requests

from backend.auth import client as auth_client
from backend.auth.client import AuthError
from backend.db.connection import get_admin_session, init_all_tables
from backend.db.models import Tenant
from backend.tenancy.provision import create_tenant


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
    for _slug, r in two_accounts:
        tokens = auth_client.sign_in(r["email"], r["password"])
        identity = auth_client.identity_from_claims(auth_client.verify_access_token(tokens["access_token"]))
        assert str(identity.tenant_id) == r["tenant_id"]
        assert identity.role == "tenant_admin"
        assert identity.email == r["email"]


def test_two_accounts_never_resolve_to_each_others_tenant(two_accounts):
    ids = set()
    for _, r in two_accounts:
        tokens = auth_client.sign_in(r["email"], r["password"])
        ids.add(auth_client.identity_from_claims(auth_client.verify_access_token(tokens["access_token"])).tenant_id)
    assert len(ids) == 2


def test_wrong_password_is_rejected(two_accounts):
    _, r = two_accounts[0]
    with pytest.raises(AuthError, match="Invalid email or password"):
        auth_client.sign_in(r["email"], "definitely-wrong")


def test_refresh_token_issues_a_new_valid_session(two_accounts):
    _, r = two_accounts[0]
    tokens = auth_client.sign_in(r["email"], r["password"])
    fresh = auth_client.refresh(tokens["refresh_token"])
    ident = auth_client.identity_from_claims(auth_client.verify_access_token(fresh["access_token"]))
    assert str(ident.tenant_id) == r["tenant_id"]


def test_a_user_cannot_change_their_own_tenant_via_user_metadata(two_accounts):
    """user_metadata is user-writable; app_metadata (where tenant_id lives) is not."""
    _, ra = two_accounts[0]
    _, rb = two_accounts[1]
    tokens = auth_client.sign_in(ra["email"], ra["password"])
    requests.put(f"{os.getenv('AUTH_BASE_URL')}/user",
                 headers={"Authorization": f"Bearer {tokens['access_token']}", "Content-Type": "application/json"},
                 json={"data": {"tenant_id": rb["tenant_id"]}}, timeout=10)
    tokens = auth_client.sign_in(ra["email"], ra["password"])
    ident = auth_client.identity_from_claims(auth_client.verify_access_token(tokens["access_token"]))
    assert str(ident.tenant_id) == ra["tenant_id"]
