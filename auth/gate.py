import html
import time

import streamlit as st

from auth import supabase
from auth.supabase import AuthError, Identity
from database.connection import get_db_session
from database.models import Tenant
from database.tenant_context import tenant_context

_REFRESH_MARGIN_S = 60
_SUPPORTED_LANGS = ("en", "de")


def _load_active_tenant(tenant_id) -> Tenant:
    with tenant_context(tenant_id):
        db = get_db_session()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).one_or_none()
            if tenant is None:
                raise AuthError("Your organisation could not be found. Contact support.")
            if tenant.status != "active":
                raise AuthError("Your organisation's account is suspended. Contact support.")
            db.expunge(tenant)
            return tenant
        finally:
            db.close()


def _establish_session(tokens: dict) -> Identity:
    claims = supabase.verify_access_token(tokens["access_token"])
    identity = supabase.identity_from_claims(claims)
    tenant = _load_active_tenant(identity.tenant_id)

    ss = st.session_state
    ss["identity"] = identity
    ss["tenant_id"] = str(identity.tenant_id)
    ss["tenant_name"] = tenant.name
    ss["tenant_config"] = dict(tenant.config or {})
    ss["auth_refresh_token"] = tokens.get("refresh_token")
    ss["auth_exp"] = claims["exp"]

    default_lang = ss["tenant_config"].get("language")
    if "lang" not in ss and default_lang in _SUPPORTED_LANGS:
        ss["lang"] = default_lang
    return identity


def sign_out():
    st.session_state.clear()
    st.rerun()


def _refresh_if_needed() -> None:
    ss = st.session_state
    if time.time() < ss.get("auth_exp", 0) - _REFRESH_MARGIN_S:
        return
    try:
        _establish_session(supabase.refresh(ss["auth_refresh_token"]))
    except AuthError:
        st.session_state.clear()
        st.rerun()


def _render_login() -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center'>Sign in</h2>", unsafe_allow_html=True)
        if not supabase.is_configured():
            st.error("Authentication is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY.")
            return
        with st.form("login_form"):
            email = st.text_input("Email", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            try:
                _establish_session(supabase.sign_in(email.strip(), password))
                st.rerun()
            except AuthError as e:
                st.error(str(e))


def require_login() -> Identity:
    """Return the signed-in identity, or render the login page and halt the script."""
    if st.session_state.get("identity") is not None:
        _refresh_if_needed()
        return st.session_state["identity"]
    _render_login()
    st.stop()


def render_account_menu() -> None:
    ss = st.session_state
    st.markdown(
        f"<div style='font-size:12px;color:#9ca3af;line-height:1.4'>"
        f"<b style='color:#f3f4f6'>{html.escape(ss.get('tenant_name', ''))}</b><br>"
        f"{html.escape(ss['identity'].email)}</div>",
        unsafe_allow_html=True,
    )
    if st.button("Sign out", key="signout", use_container_width=True):
        sign_out()
