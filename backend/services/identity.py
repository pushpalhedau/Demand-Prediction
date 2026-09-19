"""
Sign-in for the two kinds of user, kept strictly apart:

  * customer users belong to exactly one tenant (their login carries a tenant_id claim);
  * operators run the admin console and belong to no tenant.

A token for one kind is refused by the other. The frontend stores the returned session objects and
calls `refresh_*` before they expire; it never handles a token or talks to the auth server itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.auth import client as auth_client
from backend.auth.client import Identity, Operator
from backend.core.errors import AuthError
from backend.core.request_context import tenant_context
from backend.core.security import LoginThrottle
from backend.db.models import Tenant
from backend.db.session import session_scope
from backend.tenancy import audit

__all__ = ["AuthError", "CustomerSession", "Identity", "Operator", "OperatorSession", "auth_configured", "load_active_tenant",
           "refresh_customer", "refresh_operator", "sign_in_customer", "sign_in_operator", "tenant_is_active"]


_customer_throttle = LoginThrottle()
_operator_throttle = LoginThrottle()


@dataclass(frozen=True)
class CustomerSession:
    identity: Identity
    tenant_name: str
    tenant_config: dict
    refresh_token: str | None
    expires_at: int


@dataclass(frozen=True)
class OperatorSession:
    operator: Operator
    refresh_token: str | None
    expires_at: int


def auth_configured() -> bool:
    return auth_client.is_configured()


def load_active_tenant(tenant_id) -> Tenant:
    with tenant_context(tenant_id), session_scope() as db:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).one_or_none()
        if tenant is None:
            raise AuthError("Your organisation could not be found. Contact support.")
        if tenant.status != "active":
            raise AuthError("Your organisation's account is suspended. Contact support.")
        db.expunge(tenant)
        return tenant


def tenant_is_active(tenant_id) -> bool:
    """Cheap re-check used to enforce a suspension without waiting for the token to expire."""
    try:
        load_active_tenant(tenant_id)
    except AuthError:
        return False
    return True


def _customer_session(tokens: dict) -> CustomerSession:
    claims = auth_client.verify_access_token(tokens["access_token"])
    identity = auth_client.identity_from_claims(claims)
    tenant = load_active_tenant(identity.tenant_id)
    return CustomerSession(identity, tenant.name, dict(tenant.config or {}), tokens.get("refresh_token"),
                           int(claims["exp"]))


def _operator_session(tokens: dict) -> OperatorSession:
    claims = auth_client.verify_access_token(tokens["access_token"])
    operator = auth_client.operator_from_claims(claims)
    return OperatorSession(operator, tokens.get("refresh_token"), int(claims["exp"]))


def _guarded(throttle: LoginThrottle, email: str, attempt):
    """Run a sign-in attempt under the failed-login limiter (wrong password, wrong account kind, etc.)."""
    throttle.check(email)
    try:
        session = attempt()
    except AuthError:
        throttle.record_failure(email)
        raise
    throttle.record_success(email)
    return session


def sign_in_customer(email: str, password: str) -> CustomerSession:
    return _guarded(_customer_throttle, email, lambda: _customer_session(auth_client.sign_in(email, password)))


def refresh_customer(refresh_token: str) -> CustomerSession:
    return _customer_session(auth_client.refresh(refresh_token))


def sign_in_operator(email: str, password: str) -> OperatorSession:
    try:
        session = _guarded(_operator_throttle, email, lambda: _operator_session(auth_client.sign_in(email, password)))
    except AuthError as e:
        audit.record("operator.sign_in", actor=email.strip().lower(), outcome="denied", detail={"reason": str(e)[:80]})
        raise
    audit.record("operator.sign_in", actor=session.operator.email)
    return session


def refresh_operator(refresh_token: str) -> OperatorSession:
    return _operator_session(auth_client.refresh(refresh_token))
