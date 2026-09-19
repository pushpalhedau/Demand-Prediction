"""
PredictaX Admin Console: create customer accounts, load their data, train their models.

Run:  streamlit run admin_console/app.py --server.port 8502
Operators only. Keep it off the public internet (bind to localhost / VPN).
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

st.set_page_config(page_title="PredictaX Admin Console", layout="wide", initial_sidebar_state="expanded")

from admin_console.account_detail import render_account
from admin_console.accounts import render_accounts
from admin_console.gate import require_operator, sign_out
from utils.helpers import inject_custom_css

inject_custom_css()
operator = require_operator()

with st.sidebar:
    st.markdown("### Admin Console")
    st.caption(operator.email)
    st.markdown("Customer app: http://localhost:8501")
    if st.button("Sign out", use_container_width=True):
        sign_out()

slug = st.session_state.get("selected_slug")
if slug:
    render_account(slug, operator.email)
else:
    render_accounts()
