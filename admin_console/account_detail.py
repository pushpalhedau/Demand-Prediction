import secrets
import time
import uuid

import streamlit as st

from admin_console.accounts import REGION_LABELS, SYMBOLS, show_flash
from admin_console.import_wizard import render_import
from auth import supabase
from auth.supabase import AuthError
from ingestion.jobs import create_job, enqueue_job, get_job, list_jobs
from tenancy.provision import add_user, get_tenant, set_config, set_status
from tenancy.settings import InvalidSetting, validate_config
from tenancy.summary import account_summary


def _fmt_date(d):
    return d.strftime("%Y-%m-%d") if d else "–"


def _header(t: dict) -> None:
    badge = "Active" if t["status"] == "active" else "SUSPENDED"
    st.markdown(f"## {t['name']}")
    st.caption(f"id `{t['slug']}`  ·  {badge}  ·  created {t['created_at']:%Y-%m-%d}")
    s = account_summary(t["id"])
    c = st.columns(6)
    c[0].metric("Sales", f"{s['sales']:,}")
    c[1].metric("Dealers", f"{s['dealers']:,}")
    c[2].metric("Customers", f"{s['customers']:,}")
    c[3].metric("Inventory rows", f"{s['inventory']:,}")
    c[4].metric("Data from", f"{_fmt_date(s['first_sale'])}")
    c[5].metric("Models trained", "Yes" if s["models"] else "No")
    if not s["sales"]:
        st.warning("No data yet. Upload their files in the Import data tab. "
                   "Until then they see 'Your account is being set up'.")


def _follow_job(tenant_id, key: str) -> None:
    job = get_job(tenant_id, uuid.UUID(st.session_state[key]))
    if job is None:
        st.session_state.pop(key, None)
        return
    if job["status"] in ("queued", "running"):
        st.progress(float(job["progress"]), text=job["stage"] or "Working")
        time.sleep(1.5)
        st.rerun()
    elif job["status"] == "succeeded":
        st.success("Done.")
        for n in (job["report"] or {}).get("notes", []):
            st.info(n)
        st.session_state.pop(key, None)
    else:
        st.error(job["message"] or "Failed.")
        st.session_state.pop(key, None)


def _tab_history(t: dict, operator_email: str) -> None:
    key = f"train_job_{t['id']}"
    if key in st.session_state:
        _follow_job(t["id"], key)
    elif st.button("Retrain models now", key=f"retrain_{t['id']}",
                   help="Rebuilds the forecast-adjacent ML models from the data already loaded."):
        jid = uuid.uuid4()
        create_job(t["id"], {"train_only": True, "train": True}, created_by=operator_email, job_id=jid)
        enqueue_job(t["id"], jid)
        st.session_state[key] = str(jid)
        st.rerun()

    jobs = list_jobs(t["id"], limit=25)
    if not jobs:
        st.caption("No imports or retrains yet.")
        return
    st.dataframe(
        [{"When": j["created_at"].strftime("%Y-%m-%d %H:%M"), "Kind": j["kind"], "Status": j["status"],
          "By": j["created_by"] or "", "Loaded": ", ".join(f"{k} {v:,}" for k, v in j["loaded"].items()),
          "Message": j["message"] or " | ".join(j["notes"])} for j in jobs],
        use_container_width=True, hide_index=True,
    )


def _tab_users(t: dict) -> None:
    try:
        users = supabase.users_of_tenant(t["id"])
    except AuthError as e:
        st.error(str(e))
        return
    if users:
        st.dataframe(
            [{"Email": u["email"], "Role": (u.get("app_metadata") or {}).get("role", ""),
              "Last sign-in": (u.get("last_sign_in_at") or "never")[:16], "Created": (u.get("created_at") or "")[:10]}
             for u in users],
            use_container_width=True, hide_index=True)
    else:
        st.info("This account has no logins yet.")

    st.markdown("**Add a login**")
    with st.form(f"add_user_{t['id']}"):
        c1, c2, c3 = st.columns([2, 1, 2])
        email = c1.text_input("Email")
        role = c2.selectbox("Can", ["tenant_admin", "tenant_user"],
                            format_func={"tenant_admin": "Manage", "tenant_user": "View only"}.get)
        password = c3.text_input("Password (blank = generate)", type="password")
        if st.form_submit_button("Add login"):
            try:
                r = add_user(t["slug"], email.strip(), password or None, role)
            except (AuthError, ValueError) as e:
                st.error(str(e))
            else:
                st.session_state["flash"] = {"title": "Login added.", "email": r["email"], "password": r["password"]}
                st.rerun()

    if users:
        st.markdown("**Reset a password**")
        c1, c2 = st.columns([3, 1])
        who = c1.selectbox("Login", [u["email"] for u in users], key=f"reset_who_{t['id']}", label_visibility="collapsed")
        if c2.button("Reset", key=f"reset_{t['id']}", use_container_width=True):
            new = secrets.token_urlsafe(12)
            user = next(u for u in users if u["email"] == who)
            try:
                supabase.admin_set_password(user["id"], new)
            except AuthError as e:
                st.error(str(e))
            else:
                st.session_state["flash"] = {"title": "Password reset.", "email": who, "password": new}
                st.rerun()


def _tab_settings(t: dict) -> None:
    cfg = t["config"]
    with st.form(f"settings_{t['id']}"):
        c1, c2, c3, c4 = st.columns(4)
        currency = c1.text_input("Currency code", cfg.get("currency", "USD")).strip().upper()
        symbol = c2.text_input("Symbol", cfg.get("currency_symbol") or SYMBOLS.get(currency, currency))
        position = c3.selectbox("Symbol goes", ["prefix", "suffix"], index=1 if cfg.get("symbol_position") == "suffix" else 0)
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
                new = validate_config({"currency": currency, "currency_symbol": symbol, "symbol_position": position,
                                       "language": language, "region_label": region_label, "country_name": country,
                                       "news_gl": gl, "news_hl": language})
                set_config(t["slug"], new)
            except InvalidSetting as e:
                st.error(str(e))
            else:
                st.success("Saved. The customer sees it on their next page load.")
                st.rerun()


def _tab_access(t: dict) -> None:
    suspended = t["status"] != "active"
    if suspended:
        st.warning("This account is suspended. Its users cannot sign in.")
        if st.button("Reactivate account", type="primary", key=f"react_{t['id']}"):
            set_status(t["slug"], "active")
            st.rerun()
    else:
        st.write("Suspending blocks every login for this account. Their data is kept. "
                 "People already signed in are locked out within an hour, at their next session refresh.")
        sure = st.checkbox("I want to suspend this account", key=f"sure_{t['id']}")
        if st.button("Suspend account", disabled=not sure, key=f"susp_{t['id']}"):
            set_status(t["slug"], "suspended")
            st.rerun()


def render_account(slug: str, operator_email: str) -> None:
    try:
        t = get_tenant(slug)
    except Exception:
        st.error("That account no longer exists.")
        st.session_state.pop("selected_slug", None)
        return
    if st.button("← All accounts"):
        st.session_state.pop("selected_slug", None)
        st.rerun()
    show_flash()
    _header(t)
    tabs = st.tabs(["Import data", "History & models", "Logins", "Settings", "Access"])
    with tabs[0]:
        render_import(t["id"], operator_email)
    with tabs[1]:
        _tab_history(t, operator_email)
    with tabs[2]:
        _tab_users(t)
    with tabs[3]:
        _tab_settings(t)
    with tabs[4]:
        _tab_access(t)
