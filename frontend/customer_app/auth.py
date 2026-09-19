"""
Customer sign-in gate. Renders the login form and keeps the signed-in user in Streamlit's session state.
All token handling and tenant checks live in backend.services.identity; nothing here talks to the auth
server or the database.
"""
from __future__ import annotations

import html
import time

import streamlit as st

from backend.services import identity as identity_service
from backend.services.identity import AuthError, CustomerSession, Identity

_REFRESH_MARGIN_S = 60          # refresh the access token this long before it expires
_STATUS_RECHECK_S = 300         # re-check the account is still active this often
_SUPPORTED_LANGS = ("en", "de")


def _store(session: CustomerSession) -> None:
    ss = st.session_state
    ss["identity"] = session.identity
    ss["tenant_id"] = str(session.identity.tenant_id)
    ss["tenant_name"] = session.tenant_name
    ss["tenant_config"] = session.tenant_config
    ss["auth_refresh_token"] = session.refresh_token
    ss["auth_exp"] = session.expires_at
    ss["auth_status_checked"] = time.time()
    default_lang = session.tenant_config.get("language")
    if "lang" not in ss and default_lang in _SUPPORTED_LANGS:
        ss["lang"] = default_lang


def _force_sign_out(notice: str | None = None) -> None:
    st.session_state.clear()
    if notice:
        st.session_state["login_notice"] = notice
    st.rerun()


def sign_out() -> None:
    _force_sign_out()


def _keep_session_valid() -> None:
    ss = st.session_state
    now = time.time()
    if now >= ss.get("auth_exp", 0) - _REFRESH_MARGIN_S:
        try:
            _store(identity_service.refresh_customer(ss["auth_refresh_token"]))
        except AuthError:
            _force_sign_out("Your session has expired. Please sign in again.")
    elif now - ss.get("auth_status_checked", 0) >= _STATUS_RECHECK_S:
        # Enforce a suspension promptly instead of waiting for the token to run out.
        if identity_service.tenant_is_active(ss["identity"].tenant_id):
            ss["auth_status_checked"] = now
        else:
            _force_sign_out("Your organisation's account is suspended. Contact support.")


def _render_login() -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center'>Sign in</h2>", unsafe_allow_html=True)
        notice = st.session_state.pop("login_notice", None)
        if notice:
            st.warning(notice)
        if not identity_service.auth_configured():
            st.error("Authentication is not configured. Please contact support.")
            return
        with st.form("login_form"):
            email = st.text_input("Email", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            try:
                _store(identity_service.sign_in_customer(email.strip(), password))
            except AuthError as e:
                st.error(str(e))
            else:
                st.rerun()


def require_login() -> Identity:
    """Return the signed-in identity, or render the login page and halt the script."""
    if st.session_state.get("identity") is not None:
        _keep_session_valid()
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
