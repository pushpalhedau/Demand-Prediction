"""Accounts list and account creation."""
from __future__ import annotations

import streamlit as st

from backend.services import accounts as accounts_service
from backend.services.accounts import CURRENCY_SYMBOLS, REGION_LABELS, AuthError, InvalidSetting


def show_flash() -> None:
    """One-time display of credentials that must not be shown again."""
    flash = st.session_state.pop("flash", None)
    if not flash:
        return
    st.success(flash["title"])
    st.code(f"Email:    {flash['email']}\nPassword: {flash['password']}", language=None)
    st.caption("Copy these now. The password is not stored anywhere you can read it again.")


def _create_form() -> None:
    with st.form("create_account", clear_on_submit=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Account name", placeholder="Acme Motors Group")
        slug = c2.text_input("Short id (letters, digits, hyphens)", placeholder="acme-motors")
        c1, c2 = st.columns(2)
        email = c1.text_input("First admin's email")
        password = c2.text_input("Password (leave blank to generate one)", type="password")
        c1, c2, c3, c4 = st.columns(4)
        currency = c1.text_input("Currency code", "USD").strip().upper()
        symbol = c2.text_input("Symbol (blank = automatic)")
        language = c3.selectbox("Language", ["en", "de"], format_func={"en": "English", "de": "Deutsch"}.get)
        region_label = c4.selectbox("Regions are called", REGION_LABELS)
        c1, c2 = st.columns(2)
        country = c1.text_input("Country (for local news)", placeholder="United Kingdom")
        gl = c2.text_input("Country code (2 letters, for news)", placeholder="GB", max_chars=2).strip().upper()
        submitted = st.form_submit_button("Create account", type="primary")

    if not submitted:
        return
    if not name.strip() or not email.strip():
        st.error("Account name and the first admin's email are required.")
        return
    config = {"currency": currency, "currency_symbol": symbol.strip() or CURRENCY_SYMBOLS.get(currency, currency),
              "language": language, "region_label": region_label, "country_name": country.strip(),
              "news_gl": gl, "news_hl": language}
    try:
        created = accounts_service.create_account(name, slug.strip(), email, password, config)
    except (InvalidSetting, ValueError, AuthError) as e:
        st.error(str(e))
        return
    st.session_state["flash"] = {"title": f"Account '{name.strip()}' created. Next: upload their data.",
                                 "email": created["email"], "password": created["password"]}
    st.session_state["selected_slug"] = created["slug"]
    st.rerun()


def render_accounts() -> None:
    st.markdown("## Accounts")
    show_flash()
    with st.expander("Create a new account", expanded=False):
        _create_form()

    accounts = accounts_service.list_accounts()
    if not accounts:
        st.info("No accounts yet. Create the first one above.")
        return
    st.dataframe(
        [{"Name": a["name"], "Id": a["slug"], "Status": a["status"],
          "Currency": a["config"].get("currency", ""), "Language": a["config"].get("language", ""),
          "Created": a["created_at"].strftime("%Y-%m-%d")} for a in accounts],
        use_container_width=True, hide_index=True,
    )
    labels = {f"{a['name']}  ({a['slug']})": a["slug"] for a in accounts}
    c1, c2 = st.columns([3, 1])
    pick = c1.selectbox("Open an account", list(labels), label_visibility="collapsed")
    if c2.button("Open", type="primary", use_container_width=True):
        st.session_state["selected_slug"] = labels[pick]
        st.rerun()
