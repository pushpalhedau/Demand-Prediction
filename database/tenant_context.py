import uuid
from contextlib import contextmanager
from contextvars import ContextVar

_current: ContextVar = ContextVar("predictax_tenant_id", default=None)


class TenantNotSet(RuntimeError):
    pass


def _coerce(tenant_id) -> uuid.UUID:
    return tenant_id if isinstance(tenant_id, uuid.UUID) else uuid.UUID(str(tenant_id))


@contextmanager
def tenant_context(tenant_id):
    """Scope all DB work in the block to one tenant (workers, scripts, tests)."""
    token = _current.set(_coerce(tenant_id))
    try:
        yield
    finally:
        _current.reset(token)


def current_tenant_id():
    """
    Resolve the active tenant: an explicit tenant_context() wins, otherwise the
    logged-in Streamlit session. Returns None when neither is set, in which case
    Postgres row-level security returns zero rows (fails closed).
    """
    explicit = _current.get()
    if explicit is not None:
        return explicit
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            return None
        import streamlit as st
        tid = st.session_state.get("tenant_id")
        return _coerce(tid) if tid else None
    except Exception:
        return None


def require_tenant_id() -> uuid.UUID:
    tid = current_tenant_id()
    if tid is None:
        raise TenantNotSet("No tenant is active for this request.")
    return tid
