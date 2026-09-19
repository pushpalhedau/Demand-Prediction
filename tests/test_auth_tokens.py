import time
import uuid

import jwt
import pytest

from auth import supabase
from auth.supabase import AuthError

SECRET = "test-secret-at-least-32-bytes-long-xxxxxxxx"


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)


def _token(secret=SECRET, **overrides):
    claims = {"sub": "user-1", "email": "a@b.com", "aud": "authenticated", "exp": int(time.time()) + 600,
              "app_metadata": {"tenant_id": str(uuid.uuid4()), "role": "tenant_admin"}}
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


def test_valid_token_yields_identity_with_tenant():
    tid = uuid.uuid4()
    ident = supabase.identity_from_claims(
        supabase.verify_access_token(_token(app_metadata={"tenant_id": str(tid), "role": "tenant_user"})))
    assert ident.tenant_id == tid and ident.role == "tenant_user" and ident.email == "a@b.com"


def test_token_signed_with_wrong_key_is_rejected():
    with pytest.raises(AuthError):
        supabase.verify_access_token(_token(secret="an-attacker-key-that-is-also-32-bytes-long"))


def test_expired_token_is_rejected():
    with pytest.raises(AuthError, match="expired"):
        supabase.verify_access_token(_token(exp=int(time.time()) - 10))


def test_wrong_audience_is_rejected():
    with pytest.raises(AuthError):
        supabase.verify_access_token(_token(aud="anon"))


def test_alg_none_token_is_rejected():
    forged = jwt.encode({"sub": "x", "aud": "authenticated", "app_metadata": {"tenant_id": str(uuid.uuid4())}},
                        key=None, algorithm="none")
    with pytest.raises(AuthError):
        supabase.verify_access_token(forged)


def test_user_metadata_cannot_set_the_tenant():
    claims = supabase.verify_access_token(_token(
        app_metadata={}, user_metadata={"tenant_id": str(uuid.uuid4())}))
    with pytest.raises(AuthError, match="not linked"):
        supabase.identity_from_claims(claims)


def test_malformed_tenant_id_is_rejected():
    with pytest.raises(AuthError):
        supabase.identity_from_claims({"sub": "u", "app_metadata": {"tenant_id": "not-a-uuid"}})
