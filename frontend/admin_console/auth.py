"""
Operator sign-in gate for the admin console. Operators only: a customer login is rejected with the same
generic message as a wrong password, so the console does not reveal which accounts exist.
"""
from __future__ import annotations

import time

import streamlit as st

from backend.services import identity as identity_service
from backend.services.identity import AuthError, Operator, OperatorSession

_REFRESH_MARGIN_S = 60
_IDLE_TIMEOUT_S = 30 * 60       # an unattended console signs itself out


def _store(session: OperatorSession) -> None:
    ss = st.session_state
    ss["operator"] = session.operator
    ss["op_refresh"] = session.refresh_token
    ss["op_exp"] = session.expires_at


def sign_out() -> None:
    st.session_state.clear()
    st.rerun()


def _keep_session_valid() -> None:
    ss = st.session_state
    now = time.time()
    if now - ss.get("op_last_seen", now) > _IDLE_TIMEOUT_S:
        st.session_state.clear()
        st.session_state["login_notice"] = "Signed out after 30 minutes of inactivity."
        st.rerun()
    ss["op_last_seen"] = now
    if now >= ss.get("op_exp", 0) - _REFRESH_MARGIN_S:
        try:
            _store(identity_service.refresh_operator(ss["op_refresh"]))
        except AuthError:
            st.session_state.clear()
            st.rerun()


def _render_login() -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center'>PredictaX Admin Console</h2>", unsafe_allow_html=True)
        st.caption("Operators only.")
        notice = st.session_state.pop("login_notice", None)
        if notice:
            st.warning(notice)
        if not identity_service.auth_configured():
            st.error("Authentication is not configured. Set AUTH_BASE_URL (or SUPABASE_URL and SUPABASE_ANON_KEY).")
            return
        with st.form("operator_login"):
            email = st.text_input("Email", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            try:
                _store(identity_service.sign_in_operator(email.strip(), password))
            except AuthError as e:
                # A customer account gets the same generic message as a wrong password.
                st.error("Invalid email or password." if "cannot use" in str(e) else str(e))
            else:
                st.session_state["op_last_seen"] = time.time()
                st.rerun()


def require_operator() -> Operator:
    """Return the signed-in operator, or render the login page and halt the script."""
    if st.session_state.get("operator") is not None:
        _keep_session_valid()
        return st.session_state["operator"]
    _render_login()
    st.stop()
