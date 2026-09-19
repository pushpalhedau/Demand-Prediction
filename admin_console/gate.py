import time

import streamlit as st

from auth import supabase
from auth.supabase import AuthError, Operator

_REFRESH_MARGIN_S = 60


def _establish(tokens: dict) -> Operator:
    claims = supabase.verify_access_token(tokens["access_token"])
    operator = supabase.operator_from_claims(claims)      # rejects customer accounts
    ss = st.session_state
    ss["operator"] = operator
    ss["op_refresh"] = tokens.get("refresh_token")
    ss["op_exp"] = claims["exp"]
    return operator


def sign_out():
    st.session_state.clear()
    st.rerun()


def _refresh_if_needed() -> None:
    ss = st.session_state
    if time.time() < ss.get("op_exp", 0) - _REFRESH_MARGIN_S:
        return
    try:
        _establish(supabase.refresh(ss["op_refresh"]))
    except AuthError:
        st.session_state.clear()
        st.rerun()


def _render_login() -> None:
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center'>PredictaX Admin Console</h2>", unsafe_allow_html=True)
        st.caption("Operators only.")
        if not supabase.is_configured():
            st.error("Authentication is not configured. Set AUTH_BASE_URL (or SUPABASE_URL and SUPABASE_ANON_KEY).")
            return
        with st.form("operator_login"):
            email = st.text_input("Email", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            try:
                _establish(supabase.sign_in(email.strip(), password))
                st.rerun()
            except AuthError as e:
                # A customer account gets the same generic message as a wrong password.
                st.error("Invalid email or password." if "cannot use" in str(e) else str(e))


def require_operator() -> Operator:
    """Return the signed-in operator, or render the login page and halt the script."""
    if st.session_state.get("operator") is not None:
        _refresh_if_needed()
        return st.session_state["operator"]
    _render_login()
    st.stop()
