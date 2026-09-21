import time
import uuid

import jwt
import pytest

from backend.auth import client as auth_client
from backend.auth.client import AuthError

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
    ident = auth_client.identity_from_claims(
        auth_client.verify_access_token(_token(app_metadata={"tenant_id": str(tid), "role": "tenant_user"})))
    assert ident.tenant_id == tid and ident.role == "tenant_user" and ident.email == "a@b.com"


def test_token_signed_with_wrong_key_is_rejected():
    with pytest.raises(AuthError):
        auth_client.verify_access_token(_token(secret="an-attacker-key-that-is-also-32-bytes-long"))


def test_expired_token_is_rejected():
    with pytest.raises(AuthError, match="expired"):
        auth_client.verify_access_token(_token(exp=int(time.time()) - 10))


def test_wrong_audience_is_rejected():
    with pytest.raises(AuthError):
        auth_client.verify_access_token(_token(aud="anon"))


def test_alg_none_token_is_rejected():
    forged = jwt.encode({"sub": "x", "aud": "authenticated", "app_metadata": {"tenant_id": str(uuid.uuid4())}},
                        key=None, algorithm="none")
    with pytest.raises(AuthError):
        auth_client.verify_access_token(forged)


def test_user_metadata_cannot_set_the_tenant():
    claims = auth_client.verify_access_token(_token(
        app_metadata={}, user_metadata={"tenant_id": str(uuid.uuid4())}))
    with pytest.raises(AuthError, match="not linked"):
        auth_client.identity_from_claims(claims)


def test_malformed_tenant_id_is_rejected():
    with pytest.raises(AuthError):
        auth_client.identity_from_claims({"sub": "u", "app_metadata": {"tenant_id": "not-a-uuid"}})


# ── asymmetric (ES256/RS256) tokens: Supabase projects that use signing keys instead of a shared secret ──────────

def _ec_keypair():
    from cryptography.hazmat.primitives.asymmetric import ec
    private = ec.generate_private_key(ec.SECP256R1())
    return private, private.public_key()


class _FakeJwks:
    """Stands in for the network JWKS client: hands back the auth server's public key."""

    def __init__(self, public_key):
        self._public_key = public_key

    def get_signing_key_from_jwt(self, _token):
        class _Key:
            key = self._public_key
        return _Key()


@pytest.fixture()
def server_keys(monkeypatch):
    private, public = _ec_keypair()
    monkeypatch.setattr(auth_client, "_jwks_client", lambda: _FakeJwks(public))
    return private, public


def _es_token(private, **overrides):
    claims = {"sub": "user-1", "email": "a@b.com", "aud": "authenticated", "exp": int(time.time()) + 600,
              "app_metadata": {"tenant_id": str(uuid.uuid4()), "role": "tenant_admin"}}
    claims.update(overrides)
    return jwt.encode(claims, private, algorithm="ES256", headers={"kid": "test-key"})


def test_es256_token_from_the_auth_server_is_accepted(server_keys):
    private, _ = server_keys
    tid = uuid.uuid4()
    claims = auth_client.verify_access_token(_es_token(private, app_metadata={"tenant_id": str(tid), "role": "tenant_user"}))
    assert auth_client.identity_from_claims(claims).tenant_id == tid


def test_es256_token_signed_by_another_key_is_rejected(server_keys):
    other_private, _ = _ec_keypair()
    with pytest.raises(AuthError):
        auth_client.verify_access_token(_es_token(other_private))


def test_expired_es256_token_is_rejected(server_keys):
    private, _ = server_keys
    with pytest.raises(AuthError, match="expired"):
        auth_client.verify_access_token(_es_token(private, exp=int(time.time()) - 10))


def test_es256_token_with_wrong_audience_is_rejected(server_keys):
    private, _ = server_keys
    with pytest.raises(AuthError):
        auth_client.verify_access_token(_es_token(private, aud="anon"))


def test_es256_works_without_any_shared_secret(server_keys, monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    private, _ = server_keys
    assert auth_client.verify_access_token(_es_token(private))["sub"] == "user-1"


def test_hs256_token_cannot_be_forged_with_the_public_key_as_secret(server_keys):
    """Classic algorithm-confusion attack: HMAC-sign a token using the (public) verification key as the secret.

    PyJWT itself refuses to build such a token, so it is assembled by hand, the way an attacker would."""
    import base64
    import hashlib
    import hmac
    import json

    from cryptography.hazmat.primitives import serialization
    _, public = server_keys
    pem = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    signing_input = (b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()) + b"."
                     + b64(json.dumps({"sub": "attacker", "aud": "authenticated", "exp": int(time.time()) + 600,
                                       "app_metadata": {"tenant_id": str(uuid.uuid4())}}).encode()))
    forged = (signing_input + b"." + b64(hmac.new(pem, signing_input, hashlib.sha256).digest())).decode()
    with pytest.raises(AuthError):
        auth_client.verify_access_token(forged)


def test_hs256_token_is_rejected_when_no_secret_is_configured(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    with pytest.raises(AuthError):
        auth_client.verify_access_token(_token())


def test_unknown_algorithm_is_rejected(server_keys):
    """HS512 is neither of the two accepted families, so it is refused before any key is consulted."""
    with pytest.raises(AuthError):
        auth_client.verify_access_token(jwt.encode({"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 600},
                                                   SECRET, algorithm="HS512"))


def test_garbage_token_is_rejected():
    with pytest.raises(AuthError):
        auth_client.verify_access_token("not.a.jwt")
