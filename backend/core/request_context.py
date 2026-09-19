"""
Per-request scope: WHICH tenant a call is for, and how to present its numbers.

The backend never reads a web framework's session. Whoever drives it (a Streamlit page run, an RQ
worker, a CLI command) states the scope explicitly:

    bind_request(profile, language)     one page run for a signed-in user
    with tenant_context(tenant_id):     a worker / operator action on one named tenant

The scope lives in ContextVars, so concurrent sessions cannot see each other's. With no scope set,
`current_tenant_id()` is None and Postgres row-level security returns zero rows (fail closed).
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from backend.core.errors import TenantNotSet

DEFAULT_LANGUAGE = "en"


def _coerce(tenant_id: Any) -> uuid.UUID:
    return tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))


@dataclass(frozen=True)
class TenantProfile:
    """A tenant's presentation settings (from tenants.config) plus its identity."""

    tenant_id: uuid.UUID
    name: str = ""
    currency: str = "EUR"
    currency_symbol: str = "€"
    symbol_position: str | None = None      # "prefix" | "suffix" | None = follow the language
    language: str = DEFAULT_LANGUAGE
    region_label: str | None = None
    country_name: str = ""
    news_hl: str | None = None
    news_gl: str | None = None

    @classmethod
    def from_config(cls, tenant_id: Any, name: str, config: dict | None) -> TenantProfile:
        c = config or {}
        return cls(
            tenant_id=_coerce(tenant_id),
            name=name or "",
            currency=c.get("currency") or "EUR",
            currency_symbol=c.get("currency_symbol") or "€",
            symbol_position=c.get("symbol_position"),
            language=c.get("language") or DEFAULT_LANGUAGE,
            region_label=c.get("region_label"),
            country_name=c.get("country_name") or "",
            news_hl=c.get("news_hl"),
            news_gl=c.get("news_gl"),
        )


_explicit_tenant: ContextVar[uuid.UUID | None] = ContextVar("predictax_explicit_tenant", default=None)
_profile: ContextVar[TenantProfile | None] = ContextVar("predictax_profile", default=None)
_language: ContextVar[str | None] = ContextVar("predictax_language", default=None)


@contextmanager
def tenant_context(tenant_id: Any) -> Iterator[None]:
    """Scope all backend work in the block to one tenant (workers, operator actions, scripts, tests)."""
    token = _explicit_tenant.set(_coerce(tenant_id))
    try:
        yield
    finally:
        _explicit_tenant.reset(token)


def bind_request(profile: TenantProfile, language: str | None = None) -> None:
    """Scope the rest of this page run to a signed-in user's tenant."""
    _profile.set(profile)
    _language.set(language)


def clear_request() -> None:
    """Drop any scope. Call at the top of every page run, before authentication decides who this is."""
    _profile.set(None)
    _language.set(None)


def set_language(language: str) -> None:
    _language.set(language)


def current_tenant_id() -> uuid.UUID | None:
    explicit = _explicit_tenant.get()
    if explicit is not None:
        return explicit
    profile = _profile.get()
    return profile.tenant_id if profile else None


def current_profile() -> TenantProfile | None:
    """The bound profile, unless an explicit tenant_context() names a DIFFERENT tenant (never mix them)."""
    profile = _profile.get()
    explicit = _explicit_tenant.get()
    if profile is None or (explicit is not None and explicit != profile.tenant_id):
        return None
    return profile


def current_language() -> str:
    return _language.get() or (current_profile().language if current_profile() else DEFAULT_LANGUAGE)


def require_tenant_id() -> uuid.UUID:
    tenant_id = current_tenant_id()
    if tenant_id is None:
        raise TenantNotSet("No tenant is active for this request.")
    return tenant_id
