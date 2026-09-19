"""
PredictaX Admin Console: create customer accounts, load their data, train their models.

Run:  streamlit run frontend/admin_console/main.py --server.port 8502 --server.maxUploadSize 500
Operators only. Keep it off the public internet (bind to localhost / VPN).
"""
import streamlit as st

st.set_page_config(page_title="PredictaX Admin Console", layout="wide", initial_sidebar_state="expanded")

from backend.core.log import configure_logging
from backend.core.request_context import bind_actor, clear_request
from frontend.admin_console.auth import require_operator, sign_out
from frontend.admin_console.views.account_detail import render_account
from frontend.admin_console.views.accounts import render_accounts
from frontend.admin_console.views.audit_log import render_audit_log
from frontend.shared.ui import inject_custom_css

configure_logging()
inject_custom_css()
clear_request()
operator = require_operator()
bind_actor(operator.email)          # every audited action in this page run is attributed to this operator

with st.sidebar:
    st.markdown("### Admin Console")
    st.caption(operator.email)
    page = st.radio("Section", ["Accounts", "Audit log"], label_visibility="collapsed", key="admin_section")
    st.markdown("Customer app: http://localhost:8501")
    if st.button("Sign out", use_container_width=True):
        sign_out()

if page == "Audit log":
    render_audit_log()
elif st.session_state.get("selected_slug"):
    render_account(st.session_state["selected_slug"], operator.email)
else:
    render_accounts()
