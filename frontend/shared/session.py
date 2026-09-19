"""Bridge between a Streamlit session and the backend's request scope."""
from __future__ import annotations

import streamlit as st

from backend.core.request_context import TenantProfile, bind_request, clear_request
from frontend.shared.i18n import get_lang


def reset_backend_scope() -> None:
    """First thing in every page run: forget any tenant left over from a previous run on this thread."""
    clear_request()


def bind_backend_scope() -> None:
    """After sign-in: tell the backend which tenant (and presentation profile) this page run is for."""
    ss = st.session_state
    tenant_id = ss.get("tenant_id")
    if not tenant_id:
        clear_request()
        return
    bind_request(TenantProfile.from_config(tenant_id, ss.get("tenant_name", ""), ss.get("tenant_config")))
    get_lang()      # resolves the UI language and publishes it to the backend scope
