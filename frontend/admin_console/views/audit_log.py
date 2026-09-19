"""Read-only view of the operator audit trail."""
from __future__ import annotations

import json

import streamlit as st

from backend.services import accounts as accounts_service


def render_audit_log() -> None:
    st.markdown("## Audit log")
    st.caption("Every operator action, newest first. Records cannot be edited or deleted.")
    accounts = ["All accounts"] + [a["slug"] for a in accounts_service.list_accounts()]
    c1, c2 = st.columns([2, 1])
    account = c1.selectbox("Account", accounts, label_visibility="collapsed")
    limit = c2.selectbox("Show", [100, 250, 500], label_visibility="collapsed", format_func=lambda n: f"Last {n}")
    events = accounts_service.audit_trail(limit=limit, account=None if account == "All accounts" else account)
    if not events:
        st.info("No events yet.")
        return
    st.dataframe(
        [{"When (UTC)": e["at"].strftime("%Y-%m-%d %H:%M:%S"), "Who": e["actor"], "Action": e["action"],
          "Account": e["account"], "Result": e["outcome"],
          "Detail": json.dumps(e["detail"], default=str) if e["detail"] else ""} for e in events],
        use_container_width=True, hide_index=True,
    )
