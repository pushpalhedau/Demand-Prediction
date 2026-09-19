"""One customer account: import data, history and retraining, logins, settings, access."""
from __future__ import annotations

import time

import streamlit as st

from backend.services import accounts as accounts_service
from backend.services import imports as imports_service
from backend.services.accounts import CURRENCY_SYMBOLS, REGION_LABELS, AuthError, InvalidSetting
from frontend.admin_console.views.accounts import show_flash
from frontend.admin_console.views.import_wizard import render_import


def _fmt_date(d) -> str:
    return d.strftime("%Y-%m-%d") if d else "–"


def _header(account: dict) -> None:
    badge = "Active" if account["status"] == "active" else "SUSPENDED"
    st.markdown(f"## {account['name']}")
    st.caption(f"id `{account['slug']}`  ·  {badge}  ·  created {account['created_at']:%Y-%m-%d}")
    summary = accounts_service.account_summary(account["id"])
    cols = st.columns(6)
    cols[0].metric("Sales", f"{summary['sales']:,}")
    cols[1].metric("Dealers", f"{summary['dealers']:,}")
    cols[2].metric("Customers", f"{summary['customers']:,}")
    cols[3].metric("Inventory rows", f"{summary['inventory']:,}")
    cols[4].metric("Data from", _fmt_date(summary["first_sale"]))
    cols[5].metric("Models trained", "Yes" if summary["models"] else "No")
    if not summary["sales"]:
        st.warning("No data yet. Upload their files in the Import data tab. "
                   "Until then they see 'Your account is being set up'.")


def _follow_job(tenant_id, key: str) -> None:
    job = imports_service.job_status(tenant_id, st.session_state[key])
    if job is None:
        st.session_state.pop(key, None)
        return
    if job["status"] in ("queued", "running"):
        st.progress(float(job["progress"]), text=job["stage"] or "Working")
        time.sleep(1.5)
        st.rerun()
    elif job["status"] == "succeeded":
        st.success("Done.")
        for note in (job["report"] or {}).get("notes", []):
            st.info(note)
        st.session_state.pop(key, None)
    else:
        st.error(job["message"] or "Failed.")
        st.session_state.pop(key, None)


def _tab_history(account: dict, operator_email: str) -> None:
    key = f"train_job_{account['id']}"
    if key in st.session_state:
        _follow_job(account["id"], key)
    elif st.button("Retrain models now", key=f"retrain_{account['id']}",
                   help="Rebuilds the ML models from the data already loaded."):
        st.session_state[key] = imports_service.start_retrain(account["id"], operator_email)
        st.rerun()

    jobs = imports_service.recent_jobs(account["id"], limit=25)
    if not jobs:
        st.caption("No imports or retrains yet.")
        return
    st.dataframe(
        [{"When": j["created_at"].strftime("%Y-%m-%d %H:%M"), "Kind": j["kind"], "Status": j["status"],
          "By": j["created_by"] or "", "Loaded": ", ".join(f"{k} {v:,}" for k, v in j["loaded"].items()),
          "Message": j["message"] or " | ".join(j["notes"])} for j in jobs],
        use_container_width=True, hide_index=True,
    )


def _tab_users(account: dict) -> None:
    try:
        users = accounts_service.list_logins(account["id"])
    except AuthError as e:
        st.error(str(e))
        return
    if users:
        st.dataframe([{"Email": u["email"], "Role": u["role"], "Last sign-in": u["last_sign_in"],
                       "Created": u["created"]} for u in users], use_container_width=True, hide_index=True)
    else:
        st.info("This account has no logins yet.")

    st.markdown("**Add a login**")
    with st.form(f"add_user_{account['id']}"):
        c1, c2, c3 = st.columns([2, 1, 2])
        email = c1.text_input("Email")
        role = c2.selectbox("Can", ["tenant_admin", "tenant_user"],
                            format_func={"tenant_admin": "Manage", "tenant_user": "View only"}.get)
        password = c3.text_input("Password (blank = generate)", type="password")
        if st.form_submit_button("Add login"):
            try:
                created = accounts_service.add_login(account["slug"], email, password, role)
            except (AuthError, ValueError) as e:
                st.error(str(e))
            else:
                st.session_state["flash"] = {"title": "Login added.", "email": created["email"],
                                             "password": created["password"]}
                st.rerun()

    if users:
        st.markdown("**Reset a password**")
        c1, c2 = st.columns([3, 1])
        who = c1.selectbox("Login", [u["email"] for u in users], key=f"reset_who_{account['id']}",
                           label_visibility="collapsed")
        if c2.button("Reset", key=f"reset_{account['id']}", use_container_width=True):
            user = next(u for u in users if u["email"] == who)
            try:
                new_password = accounts_service.reset_login_password(user["id"])
            except AuthError as e:
                st.error(str(e))
            else:
                st.session_state["flash"] = {"title": "Password reset.", "email": who, "password": new_password}
                st.rerun()


def _tab_settings(account: dict) -> None:
    cfg = account["config"]
    with st.form(f"settings_{account['id']}"):
        c1, c2, c3, c4 = st.columns(4)
        currency = c1.text_input("Currency code", cfg.get("currency", "USD")).strip().upper()
        symbol = c2.text_input("Symbol", cfg.get("currency_symbol") or CURRENCY_SYMBOLS.get(currency, currency))
        position = c3.selectbox("Symbol goes", ["prefix", "suffix"],
                                index=1 if cfg.get("symbol_position") == "suffix" else 0)
        language = c4.selectbox("Language", ["en", "de"], index=["en", "de"].index(cfg.get("language", "en")),
                                format_func={"en": "English", "de": "Deutsch"}.get)
        c1, c2, c3 = st.columns(3)
        current = cfg.get("region_label", "Region")
        region_label = c1.selectbox("Regions are called", REGION_LABELS,
                                    index=REGION_LABELS.index(current) if current in REGION_LABELS else 0)
        country = c2.text_input("Country (for local news)", cfg.get("country_name", ""))
        gl = c3.text_input("Country code (2 letters)", cfg.get("news_gl", ""), max_chars=2).strip().upper()
        if st.form_submit_button("Save settings", type="primary"):
            try:
                accounts_service.update_account_settings(account["slug"], {
                    "currency": currency, "currency_symbol": symbol, "symbol_position": position,
                    "language": language, "region_label": region_label, "country_name": country,
                    "news_gl": gl, "news_hl": language})
            except InvalidSetting as e:
                st.error(str(e))
            else:
                st.success("Saved. The customer sees it on their next page load.")
                st.rerun()


def _tab_access(account: dict) -> None:
    if account["status"] != "active":
        st.warning("This account is suspended. Its users cannot sign in.")
        if st.button("Reactivate account", type="primary", key=f"react_{account['id']}"):
            accounts_service.set_account_status(account["slug"], "active")
            st.rerun()
        return
    st.write("Suspending blocks every login for this account. Their data is kept. "
             "People already signed in are locked out within a few minutes.")
    sure = st.checkbox("I want to suspend this account", key=f"sure_{account['id']}")
    if st.button("Suspend account", disabled=not sure, key=f"susp_{account['id']}"):
        accounts_service.set_account_status(account["slug"], "suspended")
        st.rerun()


def render_account(slug: str, operator_email: str) -> None:
    try:
        account = accounts_service.get_account(slug)
    except Exception:  # noqa: BLE001 - an account deleted elsewhere: go back to the list
        st.error("That account no longer exists.")
        st.session_state.pop("selected_slug", None)
        return
    if st.button("← All accounts"):
        st.session_state.pop("selected_slug", None)
        st.rerun()
    show_flash()
    _header(account)
    tabs = st.tabs(["Import data", "History & models", "Logins", "Settings", "Access"])
    with tabs[0]:
        render_import(account["id"], operator_email)
    with tabs[1]:
        _tab_history(account, operator_email)
    with tabs[2]:
        _tab_users(account)
    with tabs[3]:
        _tab_settings(account)
    with tabs[4]:
        _tab_access(account)
