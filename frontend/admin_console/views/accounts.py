import re
import secrets

import streamlit as st

from backend.auth.client import AuthError
from backend.tenancy.provision import all_tenants, create_tenant
from backend.tenancy.settings import InvalidSetting, validate_config

SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "AED": "AED", "SAR": "SAR", "CHF": "CHF",
           "CAD": "$", "AUD": "$", "JPY": "¥", "CNY": "¥"}
REGION_LABELS = ["Region", "State", "Province", "Emirate", "Bundesland", "County"]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


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
    slug = slug.strip() or slugify(name)
    cfg = {"currency": currency, "currency_symbol": symbol.strip() or SYMBOLS.get(currency, currency),
           "language": language, "region_label": region_label, "country_name": country.strip(),
           "news_gl": gl, "news_hl": language}
    try:
        cfg = validate_config(cfg)
        password = password or secrets.token_urlsafe(12)
        r = create_tenant(slug, name.strip(), email.strip(), password, config=cfg)
    except (InvalidSetting, ValueError, AuthError) as e:
        st.error(str(e))
        return
    st.session_state["flash"] = {"title": f"Account '{name.strip()}' created. Next: upload their data.",
                                 "email": r["email"], "password": r["password"]}
    st.session_state["selected_slug"] = r["slug"]
    st.rerun()


def render_accounts() -> None:
    st.markdown("## Accounts")
    show_flash()
    with st.expander("Create a new account", expanded=False):
        _create_form()

    tenants = all_tenants()
    if not tenants:
        st.info("No accounts yet. Create the first one above.")
        return
    st.dataframe(
        [{"Name": t["name"], "Id": t["slug"], "Status": t["status"],
          "Currency": t["config"].get("currency", ""), "Language": t["config"].get("language", ""),
          "Created": t["created_at"].strftime("%Y-%m-%d")} for t in tenants],
        use_container_width=True, hide_index=True,
    )
    labels = {f"{t['name']}  ({t['slug']})": t["slug"] for t in tenants}
    c1, c2 = st.columns([3, 1])
    pick = c1.selectbox("Open an account", list(labels), label_visibility="collapsed")
    if c2.button("Open", type="primary", use_container_width=True):
        st.session_state["selected_slug"] = labels[pick]
        st.rerun()
